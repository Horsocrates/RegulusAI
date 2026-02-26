(* ========================================================= *)
(*  LINEAR LAYER VERIFICATION                                *)
(*  Part of: Regulus — Verified AI Computation                *)
(*                                                            *)
(*  E/R/R INTERPRETATION:                                     *)
(*    Elements = list of PIntervals (neuron inputs)           *)
(*    Roles    = pi_scale, pi_wdot (weighted combination)     *)
(*    Rules    = pi_wdot_width_bound (width propagation law)  *)
(*                                                            *)
(*  P4: Each interval = the number at the current step        *)
(*      Width = honest measure of indeterminacy               *)
(*      Width bound = provable limit on indeterminacy growth  *)
(*                                                            *)
(*  KEY THEOREM: width(W·x) ≤ ε · ||W||₁                     *)
(*  "Uncertainty grows at most linearly with L1-norm of       *)
(*   weights — and we can PROVE it, not just measure it."     *)
(*                                                            *)
(*  AXIOMS: NONE. Fully constructive.                         *)
(* ========================================================= *)

From ToS Require Import PInterval.

Require Import Coq.QArith.QArith.
Require Import Coq.QArith.Qabs.
Require Import Coq.QArith.Qminmax.
Require Import Coq.micromega.Lia.
Require Import Coq.ZArith.ZArith.
Require Import Coq.Setoids.Setoid.
Require Import Coq.Lists.List.
Import ListNotations.

Open Scope Q_scope.

(* ===== SECTION 1: pi_scale — scalar × interval ===== *)
(* w * [a,b] = [w*a, w*b] if w ≥ 0, [w*b, w*a] if w < 0 *)
(* Using Qmin/Qmax avoids branching in extraction. *)

Lemma pi_scale_valid_proof : forall (w : Q) (x : PInterval),
  Qmin (w * pi_lo x) (w * pi_hi x) <= Qmax (w * pi_lo x) (w * pi_hi x).
Proof.
  intros w x.
  apply Qle_trans with (w * pi_lo x).
  - apply Q.le_min_l.
  - apply Q.le_max_l.
Qed.

Definition pi_scale (w : Q) (x : PInterval) : PInterval :=
  mkPI (Qmin (w * pi_lo x) (w * pi_hi x))
       (Qmax (w * pi_lo x) (w * pi_hi x))
       (pi_scale_valid_proof w x).

Lemma Qmin_Qmult_comm : forall a b c : Q,
  Qmin (a * b) (a * c) == Qmin (b * a) (c * a).
Proof.
  intros. setoid_replace (a * b) with (b * a) by ring.
  setoid_replace (a * c) with (c * a) by ring. reflexivity.
Qed.

Lemma Qmax_Qmult_comm : forall a b c : Q,
  Qmax (a * b) (a * c) == Qmax (b * a) (c * a).
Proof.
  intros. setoid_replace (a * b) with (b * a) by ring.
  setoid_replace (a * c) with (c * a) by ring. reflexivity.
Qed.

Theorem pi_scale_correct : forall (w : Q) (x : PInterval) (v : Q),
  pi_contains x v ->
  pi_contains (pi_scale w x) (w * v).
Proof.
  intros w x v [Hl Hr].
  unfold pi_contains, pi_scale. simpl.
  destruct (Qmult_between_r (pi_lo x) (pi_hi x) w v Hl Hr) as [Hmin Hmax].
  split.
  - rewrite Qmin_Qmult_comm.
    setoid_replace (w * v) with (v * w) by ring. exact Hmin.
  - rewrite Qmax_Qmult_comm.
    setoid_replace (w * v) with (v * w) by ring. exact Hmax.
Qed.

(* ===== SECTION 2: pi_scale_width ===== *)
(* width(w * [a,b]) = |w| * width([a,b]) *)

(* Helper: Qabs_Qmult should be in stdlib, but let's prove what we need *)
Lemma Qmult_comm_pair : forall a b : Q, a * b == b * a.
Proof. intros. ring. Qed.

Lemma Qmult_le_l_neg : forall k a b : Q, k <= 0 -> a <= b -> k * b <= k * a.
Proof.
  intros k a b Hk Hab.
  setoid_replace (k * b) with (b * k) by ring.
  setoid_replace (k * a) with (a * k) by ring.
  apply Qmult_le_r_neg; assumption.
Qed.

Lemma Qmax_eq_r : forall a b : Q, a <= b -> Qmax a b == b.
Proof.
  intros a b H.
  destruct (Q.max_spec a b) as [[Hlt Hm] | [Hge Hm]]; rewrite Hm.
  - (* Qmax = b, need b == b *) reflexivity.
  - (* Qmax = a, need a == b. We have b <= a and a <= b *)
    apply Qle_antisym; assumption.
Qed.

Lemma Qmax_eq_l : forall a b : Q, b <= a -> Qmax a b == a.
Proof.
  intros a b H.
  destruct (Q.max_spec a b) as [[Hlt Hm] | [Hge Hm]]; rewrite Hm.
  - (* Qmax = b, need b == a *) apply Qle_antisym; [exact H | apply Qlt_le_weak; exact Hlt].
  - (* Qmax = a *) reflexivity.
Qed.

Lemma Qmin_eq_l : forall a b : Q, a <= b -> Qmin a b == a.
Proof.
  intros a b H.
  destruct (Q.min_spec a b) as [[Hlt Hm] | [Hge Hm]]; rewrite Hm.
  - (* Qmin = a *) reflexivity.
  - (* Qmin = b, need b == a *) apply Qle_antisym; assumption.
Qed.

Lemma Qmin_eq_r : forall a b : Q, b <= a -> Qmin a b == b.
Proof.
  intros a b H.
  destruct (Q.min_spec a b) as [[Hlt Hm] | [Hge Hm]]; rewrite Hm.
  - (* Qmin = a, need a == b *) apply Qle_antisym; [apply Qlt_le_weak; exact Hlt | exact H].
  - (* Qmin = b *) reflexivity.
Qed.

Lemma pi_scale_width : forall (w : Q) (x : PInterval),
  pi_width (pi_scale w x) == Qabs w * pi_width x.
Proof.
  intros w x.
  unfold pi_width, pi_scale. simpl.
  destruct (Qlt_le_dec w 0) as [Hw_neg | Hw_nonneg].
  - (* w < 0: w*hi <= w*lo, so max = w*lo, min = w*hi *)
    assert (Hle : w * pi_hi x <= w * pi_lo x).
    { apply Qmult_le_l_neg; [apply Qlt_le_weak; exact Hw_neg | apply pi_valid]. }
    rewrite Qmax_eq_l by exact Hle.
    rewrite Qmin_eq_r by exact Hle.
    rewrite Qabs_neg by (apply Qlt_le_weak; exact Hw_neg).
    ring.
  - (* w >= 0: w*lo <= w*hi, so max = w*hi, min = w*lo *)
    assert (Hle : w * pi_lo x <= w * pi_hi x).
    { setoid_replace (w * pi_lo x) with (pi_lo x * w) by ring.
      setoid_replace (w * pi_hi x) with (pi_hi x * w) by ring.
      apply Qmult_le_compat_r; [apply pi_valid | exact Hw_nonneg]. }
    rewrite Qmax_eq_r by exact Hle.
    rewrite Qmin_eq_l by exact Hle.
    rewrite Qabs_pos by exact Hw_nonneg.
    ring.
Qed.

(* ===== SECTION 3: pi_add_width ===== *)
(* width([a,b] + [c,d]) = width([a,b]) + width([c,d]) *)

Lemma pi_add_width : forall (a b : PInterval),
  pi_width (pi_add a b) == pi_width a + pi_width b.
Proof.
  intros a b.
  unfold pi_width, pi_add. simpl. ring.
Qed.

(* ===== SECTION 4: Weighted dot product (scalar weights × interval inputs) ===== *)

(* Dot product with SCALAR weights and INTERVAL inputs *)
Fixpoint pi_wdot (ws : list Q) (xs : list PInterval) : PInterval :=
  match ws, xs with
  | [], _ => pi_point 0
  | _, [] => pi_point 0
  | w :: ws', x :: xs' => pi_add (pi_scale w x) (pi_wdot ws' xs')
  end.

(* Standard dot product for specification *)
Fixpoint qdot (ws vs : list Q) : Q :=
  match ws, vs with
  | [], _ => 0
  | _, [] => 0
  | w :: ws', v :: vs' => w * v + qdot ws' vs'
  end.

(* Correctness of pi_wdot *)
Theorem pi_wdot_correct : forall (ws : list Q) (xs : list PInterval) (vs : list Q),
  length ws = length xs ->
  length xs = length vs ->
  Forall2 pi_contains xs vs ->
  pi_contains (pi_wdot ws xs) (qdot ws vs).
Proof.
  intro ws. induction ws as [| w ws' IH]; intros xs vs Hlen1 Hlen2 HF.
  - simpl. unfold pi_contains, pi_point. simpl. split; apply Qle_refl.
  - destruct xs as [| x xs']; [simpl in Hlen1; discriminate |].
    destruct vs as [| v vs']; [simpl in Hlen2; discriminate |].
    inversion HF. subst.
    simpl. apply pi_add_correct.
    + apply pi_scale_correct. assumption.
    + apply IH; [simpl in Hlen1; lia | simpl in Hlen2; lia | assumption].
Qed.

(* ===== SECTION 5: Width bound for pi_wdot ===== *)
(* THE MAIN THEOREM *)

(* L1-weighted sum of widths *)
Fixpoint weighted_width_sum (ws : list Q) (xs : list PInterval) : Q :=
  match ws, xs with
  | [], _ => 0
  | _, [] => 0
  | w :: ws', x :: xs' => Qabs w * pi_width x + weighted_width_sum ws' xs'
  end.

(* Width of pi_wdot = weighted_width_sum (exact equality, not just bound) *)
Theorem pi_wdot_width : forall (ws : list Q) (xs : list PInterval),
  length ws = length xs ->
  pi_width (pi_wdot ws xs) == weighted_width_sum ws xs.
Proof.
  intros ws.
  induction ws as [| w ws' IH].
  - (* ws = [] *)
    intros. simpl. unfold pi_width, pi_point. simpl. ring.
  - (* ws = w :: ws' *)
    intros [| x xs'] Hlen.
    + simpl in Hlen. discriminate.
    + simpl. rewrite pi_add_width.
      rewrite pi_scale_width.
      rewrite IH by (simpl in Hlen; lia).
      reflexivity.
Qed.

(* Corollary: width bound (≤ version, for external use) *)
Theorem pi_wdot_width_bound : forall (ws : list Q) (xs : list PInterval),
  length ws = length xs ->
  pi_width (pi_wdot ws xs) <= weighted_width_sum ws xs.
Proof.
  intros ws xs Hlen.
  rewrite pi_wdot_width by exact Hlen.
  apply Qle_refl.
Qed.

(* ===== SECTION 6: L1-norm and uniform bound ===== *)

(* L1-norm of a list of weights *)
Fixpoint q_l1_norm (ws : list Q) : Q :=
  match ws with
  | [] => 0
  | w :: ws' => Qabs w + q_l1_norm ws'
  end.

(* Helper: if every width ≤ eps, then weighted_width_sum ≤ eps × l1_norm *)
Lemma weighted_sum_le_eps_l1 : forall (ws : list Q) (xs : list PInterval) (eps : Q),
  length ws = length xs ->
  (forall x, In x xs -> pi_width x <= eps) ->
  0 <= eps ->
  weighted_width_sum ws xs <= eps * q_l1_norm ws.
Proof.
  intro ws. induction ws as [| w ws' IH]; intros xs eps Hlen Hwidth Heps.
  - simpl. setoid_replace (eps * 0) with 0 by ring. apply Qle_refl.
  - destruct xs as [| x xs'].
    + simpl in Hlen. discriminate.
    + simpl.
      assert (Hxw : pi_width x <= eps).
      { apply Hwidth. left. reflexivity. }
      assert (Hrec : weighted_width_sum ws' xs' <= eps * q_l1_norm ws').
      { apply IH.
        - simpl in Hlen. lia.
        - intros x0 Hin. apply Hwidth. right. exact Hin.
        - exact Heps. }
      (* Goal: |w| * width(x) + wws ws' xs' <= eps * (|w| + l1 ws') *)
      setoid_replace (eps * (Qabs w + q_l1_norm ws'))
        with (eps * Qabs w + eps * q_l1_norm ws') by ring.
      apply Qplus_le_compat.
      * (* |w| * width(x) <= eps * |w| = |w| * eps *)
        setoid_replace (eps * Qabs w) with (Qabs w * eps) by ring.
        setoid_replace (Qabs w * pi_width x) with (pi_width x * Qabs w) by ring.
        setoid_replace (Qabs w * eps) with (eps * Qabs w) by ring.
        apply Qmult_le_compat_r.
        -- exact Hxw.
        -- apply Qabs_nonneg.
      * exact Hrec.
Qed.

(* MAIN COROLLARY: uniform width bound *)
Theorem pi_wdot_width_uniform_bound :
  forall (ws : list Q) (xs : list PInterval) (eps : Q),
  length ws = length xs ->
  (forall x, In x xs -> pi_width x <= eps) ->
  0 <= eps ->
  pi_width (pi_wdot ws xs) <= eps * q_l1_norm ws.
Proof.
  intros ws xs eps Hlen Hwidth Heps.
  apply Qle_trans with (weighted_width_sum ws xs).
  - apply pi_wdot_width_bound. exact Hlen.
  - apply weighted_sum_le_eps_l1; assumption.
Qed.

(* ===== SECTION 7: ReLU width bound ===== *)
(* ReLU does not increase width *)

Lemma pi_relu_width_bound : forall (x : PInterval),
  pi_width (pi_relu x) <= pi_width x.
Proof.
  intros x.
  unfold pi_width, pi_relu. simpl.
  (* Goal: Qmax 0 hi - Qmax 0 lo <= hi - lo *)
  destruct (Qlt_le_dec (pi_lo x) 0) as [Hlo_neg | Hlo_nonneg];
  destruct (Qlt_le_dec (pi_hi x) 0) as [Hhi_neg | Hhi_nonneg].
  - (* both < 0: relu = [0,0], width = 0 ≤ hi - lo *)
    rewrite Q.max_l by (apply Qlt_le_weak; exact Hhi_neg).
    rewrite Q.max_l by (apply Qlt_le_weak; exact Hlo_neg).
    setoid_replace (0 - 0) with 0 by ring.
    apply pi_width_nonneg.
  - (* lo < 0 ≤ hi: relu = [0, hi], width = hi ≤ hi - lo *)
    rewrite Q.max_r by exact Hhi_nonneg.
    rewrite Q.max_l by (apply Qlt_le_weak; exact Hlo_neg).
    (* Goal: hi - 0 <= hi - lo, i.e. -0 <= -lo, i.e. lo <= 0 *)
    setoid_replace (pi_hi x - 0) with (pi_hi x) by ring.
    (* pi_hi x <= pi_hi x - pi_lo x *)
    setoid_replace (pi_hi x) with (pi_hi x - 0) at 1 by ring.
    apply Qplus_le_compat.
    + apply Qle_refl.
    + apply Qopp_le_compat. apply Qlt_le_weak. exact Hlo_neg.
  - (* 0 ≤ lo, hi < 0: impossible *)
    exfalso. apply (Qlt_not_le _ _ Hhi_neg).
    apply Qle_trans with (pi_lo x); [exact Hlo_nonneg | apply pi_valid].
  - (* 0 ≤ lo ≤ hi: relu = [lo, hi], width unchanged *)
    rewrite Q.max_r by exact Hhi_nonneg.
    rewrite Q.max_r by exact Hlo_nonneg.
    apply Qle_refl.
Qed.

(* ===== VERIFICATION ===== *)
Print Assumptions pi_scale_correct.
Print Assumptions pi_scale_width.
Print Assumptions pi_add_width.
Print Assumptions pi_wdot_correct.
Print Assumptions pi_wdot_width.
Print Assumptions pi_wdot_width_bound.
Print Assumptions pi_wdot_width_uniform_bound.
Print Assumptions pi_relu_width_bound.
