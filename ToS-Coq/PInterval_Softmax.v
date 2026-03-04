(* ========================================================================= *)
(*  PInterval_Softmax: Verified Interval Softmax Bounds                     *)
(*  Part of: Regulus - Verified AI Computation                              *)
(*                                                                          *)
(*  Author:  Horsocrates | Date: February 2026                              *)
(*                                                                          *)
(*  AXIOMS: NONE. Fully constructive.                                       *)
(*                                                                          *)
(*  KEY DESIGN DECISION: Parametric over exp function.                      *)
(*  Softmax uses e^x but defining e^x : Q -> Q constructively is           *)
(*  impossible. Instead we prove bounds for ANY monotone positive            *)
(*  function f. When instantiated with np.exp, this gives exactly           *)
(*  the guarantees the Python IntervalSoftmax needs.                        *)
(*                                                                          *)
(*  APPROACH: Cross-multiplication to avoid Qdiv complexity.                *)
(*  Instead of proving f(lo)/D_max <= f(x)/D_actual, we prove the          *)
(*  equivalent: f(lo) * D_actual <= f(x) * D_max.                          *)
(*                                                                          *)
(*  COMPILE:                                                                *)
(*    coqc -Q . ToS PInterval_Softmax.v                                     *)
(*                                                                          *)
(* ========================================================================= *)

Require Import Coq.QArith.QArith.
Require Import Coq.QArith.Qminmax.
Require Import Coq.Lists.List.
Require Import Coq.Setoids.Setoid.
Require Import Coq.micromega.Lia.
Import ListNotations.
Open Scope Q_scope.


(* ===================================================================== *)
(* SECTION 1: Parametric softmax bounds                                   *)
(*                                                                        *)
(* We abstract over any function f : Q -> Q that is:                     *)
(*   1. Monotone increasing: a <= b -> f(a) <= f(b)                       *)
(*   2. Strictly positive:   0 < f(x) for all x                          *)
(*                                                                        *)
(* These properties hold for exp, and the Python IntervalSoftmax          *)
(* uses exactly this structure.                                            *)
(* ===================================================================== *)

Section SoftmaxBound.

Variable f : Q -> Q.
Hypothesis f_mono : forall a b : Q, a <= b -> f a <= f b.
Hypothesis f_pos  : forall x : Q, 0 < f x.

(* ----- Helper: f values are nonneg ----- *)
Lemma f_nonneg : forall x : Q, 0 <= f x.
Proof. intros. apply Qlt_le_weak. apply f_pos. Qed.


(* ===================================================================== *)
(* SECTION 2: Sum of f over a list                                        *)
(* ===================================================================== *)

Fixpoint f_sum (xs : list Q) : Q :=
  match xs with
  | [] => 0
  | x :: rest => f x + f_sum rest
  end.

Lemma f_sum_nonneg : forall xs : list Q, 0 <= f_sum xs.
Proof.
  induction xs as [| x rest IH]; simpl.
  - apply Qle_refl.
  - apply Qle_trans with (0 + 0).
    + setoid_replace (0 + 0) with 0 by ring. apply Qle_refl.
    + apply Qplus_le_compat. apply f_nonneg. exact IH.
Qed.

Lemma f_sum_monotone : forall xs ys : list Q,
  length xs = length ys ->
  (forall n, (n < length xs)%nat -> nth n xs 0 <= nth n ys 0) ->
  f_sum xs <= f_sum ys.
Proof.
  intros xs. induction xs as [| x rest IH]; intros ys Hlen Hle; simpl.
  - destruct ys. simpl. apply Qle_refl. simpl in Hlen. discriminate.
  - destruct ys as [| y ys']. simpl in Hlen. discriminate.
    simpl. simpl in Hlen. injection Hlen as Hlen'.
    apply Qplus_le_compat.
    + apply f_mono. apply (Hle 0%nat). simpl. lia.
    + apply IH.
      * exact Hlen'.
      * intros n Hn. apply (Hle (S n)). simpl. lia.
Qed.

(* Sum of f over all elements except index i *)
Fixpoint f_sum_except (xs : list Q) (skip : nat) : Q :=
  match xs with
  | [] => 0
  | x :: rest =>
    match skip with
    | O => f_sum rest  (* skip this element, sum the rest without skipping *)
    | S k => f x + f_sum_except rest k
    end
  end.

(* When skip >= length, f_sum_except = f_sum (nothing skipped) *)
(* We don't need this for the main theorems. *)

Lemma f_sum_except_nonneg : forall xs skip, 0 <= f_sum_except xs skip.
Proof.
  intros xs. induction xs as [| x rest IH]; intros skip; simpl.
  - apply Qle_refl.
  - destruct skip.
    + apply f_sum_nonneg.
    + apply Qle_trans with (0 + 0).
      * setoid_replace (0 + 0) with 0 by ring. apply Qle_refl.
      * apply Qplus_le_compat. apply f_nonneg. apply IH.
Qed.

(* Monotonicity: if xs[j] <= ys[j] for all j, then
   f_sum_except xs skip <= f_sum_except ys skip *)
Lemma f_sum_except_monotone : forall xs ys skip,
  length xs = length ys ->
  (forall n, (n < length xs)%nat -> nth n xs 0 <= nth n ys 0) ->
  f_sum_except xs skip <= f_sum_except ys skip.
Proof.
  intros xs. induction xs as [| x rest IH]; intros ys skip Hlen Hle; simpl.
  - destruct ys. simpl. apply Qle_refl. simpl in Hlen. discriminate.
  - destruct ys as [| y ys']. simpl in Hlen. discriminate.
    simpl in Hlen. injection Hlen as Hlen'.
    destruct skip.
    + (* skip = 0: compare f_sum rest vs f_sum ys' *)
      apply f_sum_monotone; auto.
      intros n Hn. apply (Hle (S n)). simpl. lia.
    + (* skip = S k *)
      simpl. apply Qplus_le_compat.
      * apply f_mono. apply (Hle 0%nat). simpl. lia.
      * apply IH; auto.
        intros n Hn. apply (Hle (S n)). simpl. lia.
Qed.


(* ===================================================================== *)
(* SECTION 3: Cross-multiplication lemma (the core technique)            *)
(*                                                                        *)
(* If a <= b and c <= d (all nonneg), then a * d <= b * c                *)
(* is NOT true in general. What IS true:                                  *)
(*   a <= b and d >= c  implies  a*c <= b*d  (both factors grow)          *)
(*                                                                        *)
(* For softmax lower bound we need:                                       *)
(*   f(lo) * D_actual <= f(x) * D_lower_bound                            *)
(* where D_actual = f(x_i) + sum_except f(x_j)                           *)
(* and   D_lower_bound = f(lo_i) + sum_except f(hi_j)                    *)
(*                                                                        *)
(* The trick: rewrite the cross-product inequality.                       *)
(* f(lo) * (f(x) + S_x) <= f(x) * (f(lo) + S_hi)                       *)
(* f(lo)*f(x) + f(lo)*S_x <= f(x)*f(lo) + f(x)*S_hi                    *)
(* f(lo)*S_x <= f(x)*S_hi                                                *)
(* This holds because f(lo) <= f(x) and S_x <= S_hi.                    *)
(* ===================================================================== *)

Lemma Qmul_le_compat_nonneg : forall a b c d : Q,
  0 <= a -> 0 <= c -> a <= b -> c <= d -> a * c <= b * d.
Proof.
  intros a b c d Ha Hc Hab Hcd.
  apply Qle_trans with (a * d).
  - (* a * c <= a * d: Qmult_le_compat_r wants x*z <= y*z, so commute *)
    setoid_replace (a * c) with (c * a) by ring.
    setoid_replace (a * d) with (d * a) by ring.
    apply Qmult_le_compat_r; assumption.
  - (* a * d <= b * d: already in x*z <= y*z form with z=d *)
    apply Qmult_le_compat_r.
    + exact Hab.
    + apply Qle_trans with c; assumption.
Qed.

(* The specific cross-multiplication for softmax fractions:
   f(lo) * (f(x) + S_x) <= f(x) * (f(lo) + S_hi)
   when f(lo) <= f(x) and S_x <= S_hi *)
Lemma softmax_cross_mul_lower : forall flo fx sx shi : Q,
  0 <= flo -> 0 <= fx -> 0 <= sx -> 0 <= shi ->
  flo <= fx -> sx <= shi ->
  flo * (fx + sx) <= fx * (flo + shi).
Proof.
  intros flo fx sx shi Hflo Hfx Hsx Hshi Hle_f Hle_s.
  setoid_replace (flo * (fx + sx)) with (flo * fx + flo * sx) by ring.
  setoid_replace (fx * (flo + shi)) with (fx * flo + fx * shi) by ring.
  setoid_replace (flo * fx) with (fx * flo) by ring.
  apply Qplus_le_compat.
  - apply Qle_refl.
  - apply Qmul_le_compat_nonneg; assumption.
Qed.

(* Symmetric version for upper bound:
   fx * (fhi + S_lo) <= fhi * (fx + S_x)
   when fx <= fhi and S_lo <= S_x *)
Lemma softmax_cross_mul_upper : forall fx fhi sx slo : Q,
  0 <= fx -> 0 <= fhi -> 0 <= sx -> 0 <= slo ->
  fx <= fhi -> slo <= sx ->
  fx * (fhi + slo) <= fhi * (fx + sx).
Proof.
  intros fx fhi sx slo Hfx Hfhi Hsx Hslo Hle_f Hle_s.
  setoid_replace (fx * (fhi + slo)) with (fx * fhi + fx * slo) by ring.
  setoid_replace (fhi * (fx + sx)) with (fhi * fx + fhi * sx) by ring.
  setoid_replace (fx * fhi) with (fhi * fx) by ring.
  apply Qplus_le_compat.
  - apply Qle_refl.
  - apply Qmul_le_compat_nonneg; assumption.
Qed.


(* ===================================================================== *)
(* SECTION 4: Main theorems -- stated in cross-multiplication form        *)
(*                                                                        *)
(* We state soundness using cross-multiplication rather than division,    *)
(* which is both cleaner and avoids nonzero-denominator proofs.           *)
(*                                                                        *)
(* Cross-mul form of "a/(a+d) <= b/(b+e)":                               *)
(*   a * (b + e) <= b * (a + d)                                          *)
(* ===================================================================== *)

(* ---- Lower bound soundness ---- *)
(* For component i: if lo_i <= x_i and x_j <= hi_j for all j != i,
   then f(lo_i) * D_x <= f(x_i) * D_lo
   where D_x  = f(x_i) + sum_{j!=i} f(x_j)    (actual denominator)
   and   D_lo = f(lo_i) + sum_{j!=i} f(hi_j)   (lower-bound denominator)

   This is the cross-multiplication form of:
     f(lo_i) / D_lo <= f(x_i) / D_x = softmax_i(x)
*)
Theorem interval_softmax_lower_bound :
  forall (los his xs : list Q) (idx : nat),
  length los = length his ->
  length los = length xs ->
  (forall n, (n < length los)%nat -> nth n los 0 <= nth n xs 0) ->
  (forall n, (n < length los)%nat -> nth n xs 0 <= nth n his 0) ->
  (* Cross-mul form: f(lo_i) * (f(x_i) + sum_except f(x, i))
                    <= f(x_i) * (f(lo_i) + sum_except f(hi, i)) *)
  (idx < length los)%nat ->
  f (nth idx los 0) * (f (nth idx xs 0) + f_sum_except xs idx)
  <= f (nth idx xs 0) * (f (nth idx los 0) + f_sum_except his idx).
Proof.
  intros los his xs idx Hlen1 Hlen2 Hlo Hhi Hidx.
  apply softmax_cross_mul_lower.
  - apply f_nonneg.
  - apply f_nonneg.
  - apply f_sum_except_nonneg.
  - apply f_sum_except_nonneg.
  - apply f_mono. apply Hlo. exact Hidx.
  - apply f_sum_except_monotone.
    + lia.
    + intros n Hn. apply Hhi. lia.
Qed.

(* ---- Upper bound soundness ---- *)
(* For component i: if x_i <= hi_i and lo_j <= x_j for all j != i,
   then f(x_i) * D_hi <= f(hi_i) * D_x
   where D_x  = f(x_i) + sum_{j!=i} f(x_j)    (actual denominator)
   and   D_hi = f(hi_i) + sum_{j!=i} f(lo_j)   (upper-bound denominator)

   Cross-multiplication form of:
     softmax_i(x) = f(x_i) / D_x <= f(hi_i) / D_hi
*)
Theorem interval_softmax_upper_bound :
  forall (los his xs : list Q) (idx : nat),
  length los = length his ->
  length los = length xs ->
  (forall n, (n < length los)%nat -> nth n los 0 <= nth n xs 0) ->
  (forall n, (n < length los)%nat -> nth n xs 0 <= nth n his 0) ->
  (idx < length los)%nat ->
  f (nth idx xs 0) * (f (nth idx his 0) + f_sum_except los idx)
  <= f (nth idx his 0) * (f (nth idx xs 0) + f_sum_except xs idx).
Proof.
  intros los his xs idx Hlen1 Hlen2 Hlo Hhi Hidx.
  apply softmax_cross_mul_upper.
  - apply f_nonneg.
  - apply f_nonneg.
  - apply f_sum_except_nonneg.
  - apply f_sum_except_nonneg.
  - apply f_mono. apply Hhi. exact Hidx.
  - apply f_sum_except_monotone.
    + lia.
    + intros n Hn. apply Hlo. lia.
Qed.


(* ===================================================================== *)
(* SECTION 5: Denominator positivity (needed for actual division form)    *)
(* ===================================================================== *)

Lemma denom_positive : forall (xs : list Q) (idx : nat),
  0 < f (nth idx xs 0) + f_sum_except xs idx.
Proof.
  intros xs idx.
  apply Qlt_le_trans with (f (nth idx xs 0) + 0).
  - setoid_replace (f (nth idx xs 0) + 0) with (f (nth idx xs 0)) by ring.
    apply f_pos.
  - apply Qplus_le_compat.
    + apply Qle_refl.
    + apply f_sum_except_nonneg.
Qed.


(* ===================================================================== *)
(* SECTION 6: Bounds in [0, 1]                                            *)
(*                                                                        *)
(* The softmax lower bound f(lo_i)/(f(lo_i) + S_hi) is in (0,1)          *)
(* because numerator > 0, denominator >= numerator.                       *)
(* ===================================================================== *)

(* Numerator is positive *)
Lemma softmax_bound_numerator_pos : forall (xs : list Q) (idx : nat),
  0 < f (nth idx xs 0).
Proof. intros. apply f_pos. Qed.

(* Numerator <= Denominator (cross-mul form: f(x) * 1 <= 1 * (f(x) + S)) *)
Lemma softmax_bound_le_one_cross : forall (xs : list Q) (idx : nat),
  f (nth idx xs 0) * 1 <= 1 * (f (nth idx xs 0) + f_sum_except xs idx).
Proof.
  intros.
  setoid_replace (f (nth idx xs 0) * 1) with (f (nth idx xs 0)) by ring.
  setoid_replace (1 * (f (nth idx xs 0) + f_sum_except xs idx))
    with (f (nth idx xs 0) + f_sum_except xs idx) by ring.
  setoid_replace (f (nth idx xs 0))
    with (f (nth idx xs 0) + 0) at 1 by ring.
  apply Qplus_le_compat.
  - apply Qle_refl.
  - apply f_sum_except_nonneg.
Qed.

End SoftmaxBound.


(* ===================================================================== *)
(* SECTION 7: Print Assumptions                                           *)
(* ===================================================================== *)

(* Verify all theorems are axiom-free (parametric over f) *)
Print Assumptions interval_softmax_lower_bound.
Print Assumptions interval_softmax_upper_bound.
Print Assumptions denom_positive.
Print Assumptions softmax_bound_le_one_cross.
Print Assumptions f_sum_monotone.
Print Assumptions f_sum_except_monotone.
Print Assumptions softmax_cross_mul_lower.
Print Assumptions softmax_cross_mul_upper.
