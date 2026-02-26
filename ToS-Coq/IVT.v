(* ========================================================================= *)
(*                 INTERMEDIATE VALUE THEOREM                                *)
(*              Formalization Without the Axiom of Infinity                  *)
(*                                                                           *)
(*  Part of: Theory of Systems - Coq Formalization (E/R/R Framework)         *)
(*                                                                           *)
(*  Author:  Horsocrates | Version: 3.0 (E/R/R) | Date: January 2026         *)
(*                                                                           *)
(*  STATUS: 23 Qed, 0 Admitted (100% COMPLETE)                               *)
(*                                                                           *)
(* ========================================================================= *)
(*                                                                           *)
(*  E/R/R INTERPRETATION:                                                    *)
(*  =====================                                                    *)
(*                                                                           *)
(*  IVT via bisection demonstrates P4 (Finitude):                            *)
(*                                                                           *)
(*    Elements = interval endpoints (Q values)                               *)
(*    Roles    = bisection choice (left/right based on sign)                 *)
(*    Rules    = sign change preservation (L4: sufficient reason)            *)
(*                                                                           *)
(*  ACTUALIZATION:                                                           *)
(*    Process: bisection_step (halves interval, preserves sign change)       *)
(*    Constitution: interval shrinks to zero width                           *)
(*    Product: root location (CauchyProcess converging to zero)              *)
(*                                                                           *)
(*  THEOREM: If f(a) < 0 < f(b) and f continuous, then exists c: f(c) = 0    *)
(*                                                                           *)
(*  AXIOMS: classic (L3) + Archimedean. NO Axiom of Infinity.                *)
(*                                                                           *)
(* ========================================================================= *)

Require Import Coq.QArith.QArith Coq.QArith.Qabs Coq.QArith.Qfield.
Require Import Coq.Logic.Classical_Prop.
Require Import Coq.micromega.Lia Coq.ZArith.ZArith Coq.Setoids.Setoid.
From ToS Require Import Archimedean.

Open Scope Q_scope.

(* ===== SECTION 1: DEFINITIONS ===== *)

Definition in_interval (a b : Q) (R : RealProcess) : Prop := 
  forall n : nat, a <= R n /\ R n <= b.

Definition equiv (R1 R2 : RealProcess) : Prop := 
  forall eps : Q, eps > 0 -> exists N : nat, forall n : nat,
    (n > N)%nat -> Qabs (R1 n - R2 n) < eps.

Definition ContinuousFunction := Q -> Q.

Definition uniformly_continuous_on (f : ContinuousFunction) (a b : Q) : Prop := 
  forall eps : Q, eps > 0 -> exists delta : Q, delta > 0 /\ 
    forall x y : Q, a <= x <= b -> a <= y <= b -> 
    Qabs (x - y) < delta -> Qabs (f x - f y) < eps.

Definition apply_to_process (f : ContinuousFunction) (R : RealProcess) : RealProcess := 
  fun n => f (R n).

(* ===== SECTION 2: HELPER LEMMAS ===== *)

Lemma Qpow2_0 : Qpow2 0 == 1. Proof. reflexivity. Qed.
Lemma two_nonzero : ~ (2 == 0). Proof. unfold Qeq. simpl. lia. Qed.
Lemma div_1 : forall x : Q, x / 1 == x. Proof. intro x. field. Qed.
Lemma div_2_mul : forall x y : Q, ~ y == 0 -> (x / y) / 2 == x / (2 * y). 
Proof. intros x y Hy. field. auto using two_nonzero. Qed.
Lemma Qpow2_Sn : forall n, Qpow2 (S n) == 2 * Qpow2 n. Proof. reflexivity. Qed.

Lemma pow2_mono_strict : forall m n, (m < n)%nat -> (pow2 m < pow2 n)%positive.
Proof. intros m n Hmn. induction Hmn; simpl; lia. Qed.

Lemma half_le_full : forall x : Q, 0 <= x -> x / 2 <= x.
Proof.
  intros [xn xd] Hx. unfold Qle, Qdiv, Qmult, Qinv in *. simpl in *.
  nia.
Qed.

Lemma Qle_half_sum_l : forall a b : Q, a <= b -> a <= (a + b) / 2.
Proof. intros a b H. unfold Qle, Qdiv, Qmult, Qplus, Qinv in *. simpl. nia. Qed.

Lemma Qle_half_sum_r : forall a b : Q, a <= b -> (a + b) / 2 <= b.
Proof. intros a b H. unfold Qle, Qdiv, Qmult, Qplus, Qinv in *. simpl. nia. Qed.

Lemma Qle_sub_r : forall a b c : Q, a <= b -> a - c <= b - c.
Proof.
  intros [ap aq] [bp bq] [cp cq] Hab.
  unfold Qle, Qminus, Qplus, Qopp in *. simpl in *.
  assert (Hcq : (Z.pos cq > 0)%Z) by lia.
  assert (Hbq : (Z.pos bq > 0)%Z) by lia.
  assert (Haq : (Z.pos aq > 0)%Z) by lia. nia.
Qed.

Lemma Qle_sub_l : forall a b c : Q, a <= b -> c - b <= c - a.
Proof.
  intros [ap aq] [bp bq] [cp cq] Hab.
  unfold Qle, Qminus, Qplus, Qopp in *. simpl in *.
  assert (Hcq : (Z.pos cq > 0)%Z) by lia.
  assert (Hbq : (Z.pos bq > 0)%Z) by lia.
  assert (Haq : (Z.pos aq > 0)%Z) by lia. nia.
Qed.

Lemma Qle_sub_trans : forall a b c d : Q, a <= b -> c <= d -> a - d <= b - c.
Proof.
  intros a b c d Hab Hcd. apply Qle_trans with (b - d).
  - apply Qle_sub_r. exact Hab. - apply Qle_sub_l. exact Hcd.
Qed.

Lemma Qabs_between : forall x y lo hi : Q,
  lo <= x -> x <= hi -> lo <= y -> y <= hi -> Qabs (x - y) <= hi - lo.
Proof.
  intros x y lo hi Hlx Hxh Hly Hyh. apply Qabs_case; intro Hsign.
  - apply Qle_sub_trans. exact Hxh. exact Hly.
  - setoid_replace (-(x - y)) with (y - x) by ring. apply Qle_sub_trans. exact Hyh. exact Hlx.
Qed.

(* ===== SECTION 3: BISECTION ALGORITHM ===== *)

Record BisectionState := mkBisection { bis_left : Q; bis_right : Q }.

Definition bisection_step (f : ContinuousFunction) (s : BisectionState) : BisectionState := 
  let mid := (bis_left s + bis_right s) / 2 in 
  if Qlt_le_dec (f mid) 0 then mkBisection mid (bis_right s) else mkBisection (bis_left s) mid.

Fixpoint bisection_iter (f : ContinuousFunction) (s : BisectionState) (n : nat) : BisectionState := 
  match n with O => s | S n' => bisection_step f (bisection_iter f s n') end.

Definition bisection_process (f : ContinuousFunction) (a b : Q) : RealProcess := 
  fun n => let s := bisection_iter f (mkBisection a b) n in (bis_left s + bis_right s) / 2.

(* ===== SECTION 4: WIDTH AND BOUNDS ===== *)

Lemma step_halves : forall (f : ContinuousFunction) (s : BisectionState), 
  bis_right (bisection_step f s) - bis_left (bisection_step f s) == (bis_right s - bis_left s) / 2.
Proof. intros f s. unfold bisection_step. 
  destruct (Qlt_le_dec (f ((bis_left s + bis_right s) / 2)) 0); simpl; field. Qed.

Lemma bisection_width : forall (f : ContinuousFunction) (a b : Q) (n : nat), 
  bis_right (bisection_iter f (mkBisection a b) n) - bis_left (bisection_iter f (mkBisection a b) n) == (b - a) / Qpow2 n.
Proof. intros f a b n. induction n. 
  - simpl. rewrite Qpow2_0, div_1. reflexivity. 
  - simpl. rewrite step_halves, IHn, div_2_mul, Qpow2_Sn. reflexivity. apply Qpow2_nonzero. Qed.

Lemma iter_bounds : forall (f : ContinuousFunction) (a b : Q) (n : nat), a <= b ->
  a <= bis_left (bisection_iter f (mkBisection a b) n) /\ 
  bis_right (bisection_iter f (mkBisection a b) n) <= b /\ 
  bis_left (bisection_iter f (mkBisection a b) n) <= bis_right (bisection_iter f (mkBisection a b) n).
Proof.
  intros f a b n Hab. induction n.
  - simpl. split. apply Qle_refl. split. apply Qle_refl. exact Hab.
  - simpl. destruct IHn as [Ha' [Hb' Hlr]].
    set (prev := bisection_iter f (mkBisection a b) n) in *.
    unfold bisection_step. destruct (Qlt_le_dec (f ((bis_left prev + bis_right prev) / 2)) 0); simpl; (split; [|split]).
    + apply Qle_trans with (bis_left prev). exact Ha'. apply Qle_half_sum_l. exact Hlr.
    + exact Hb'. + apply Qle_half_sum_r. exact Hlr.
    + exact Ha'. + apply Qle_trans with (bis_right prev). apply Qle_half_sum_r. exact Hlr. exact Hb'.
    + apply Qle_half_sum_l. exact Hlr.
Qed.

Lemma step_nested : forall (f : ContinuousFunction) (s : BisectionState),
  bis_left s <= bis_right s ->
  bis_left s <= bis_left (bisection_step f s) /\ bis_right (bisection_step f s) <= bis_right s.
Proof.
  intros f s Hlr. unfold bisection_step.
  destruct (Qlt_le_dec (f ((bis_left s + bis_right s) / 2)) 0); simpl; split.
  - apply Qle_half_sum_l. exact Hlr. - apply Qle_refl.
  - apply Qle_refl. - apply Qle_half_sum_r. exact Hlr.
Qed.

Lemma iter_nested : forall (f : ContinuousFunction) (a b : Q) (m n : nat), a <= b -> (m <= n)%nat ->
  bis_left (bisection_iter f (mkBisection a b) m) <= bis_left (bisection_iter f (mkBisection a b) n) /\
  bis_right (bisection_iter f (mkBisection a b) n) <= bis_right (bisection_iter f (mkBisection a b) m).
Proof.
  intros f a b m n Hab Hmn. induction Hmn.
  - split; apply Qle_refl.
  - destruct IHHmn as [Hl Hr].
    pose proof (iter_bounds f a b m0 Hab) as [_ [_ Hlr_m0]].
    pose proof (step_nested f (bisection_iter f (mkBisection a b) m0) Hlr_m0) as [Hstep_l Hstep_r].
    simpl. split.
    + apply Qle_trans with (bis_left (bisection_iter f (mkBisection a b) m0)). exact Hl. exact Hstep_l.
    + apply Qle_trans with (bis_right (bisection_iter f (mkBisection a b) m0)). exact Hstep_r. exact Hr.
Qed.

Lemma bisection_in_interval : forall (f : ContinuousFunction) (a b : Q), a <= b -> 
  in_interval a b (bisection_process f a b).
Proof.
  intros f a b Hab n.
  pose proof (iter_bounds f a b n Hab) as [Ha [Hb Hlr]]. split.
  - apply Qle_trans with (bis_left (bisection_iter f (mkBisection a b) n)). 
    exact Ha. apply Qle_half_sum_l. exact Hlr.
  - apply Qle_trans with (bis_right (bisection_iter f (mkBisection a b) n)). 
    apply Qle_half_sum_r. exact Hlr. exact Hb.
Qed.

(* ===== SECTION 5: CAUCHY PROPERTY ===== *)

Lemma bisection_shrinks : forall (f : ContinuousFunction) (a b : Q) (m n : nat),
  a < b -> (m <= n)%nat ->
  Qabs (bisection_process f a b m - bisection_process f a b n) <= (b - a) / Qpow2 m.
Proof.
  intros f a b m n Hab Hmn. unfold bisection_process.
  pose proof (iter_bounds f a b m (Qlt_le_weak _ _ Hab)) as [_ [_ Hlrm]].
  pose proof (iter_bounds f a b n (Qlt_le_weak _ _ Hab)) as [_ [_ Hlrn]].
  pose proof (iter_nested f a b m n (Qlt_le_weak _ _ Hab) Hmn) as [Hnest_l Hnest_r].
  set (lm := bis_left (bisection_iter f (mkBisection a b) m)).
  set (rm := bis_right (bisection_iter f (mkBisection a b) m)).
  set (ln := bis_left (bisection_iter f (mkBisection a b) n)).
  set (rn := bis_right (bisection_iter f (mkBisection a b) n)).
  assert (Hmidm_l : lm <= (lm + rm) / 2) by (apply Qle_half_sum_l; exact Hlrm).
  assert (Hmidm_r : (lm + rm) / 2 <= rm) by (apply Qle_half_sum_r; exact Hlrm).
  assert (Hmidn_l : lm <= (ln + rn) / 2).
  { apply Qle_trans with ln. exact Hnest_l. apply Qle_half_sum_l. exact Hlrn. }
  assert (Hmidn_r : (ln + rn) / 2 <= rm).
  { apply Qle_trans with rn. apply Qle_half_sum_r. exact Hlrn. exact Hnest_r. }
  apply Qle_trans with (rm - lm).
  - apply Qabs_between; assumption.
  - pose proof (bisection_width f a b m) as Hw. 
    unfold lm, rm. rewrite Hw. apply Qle_refl.
Qed.

Lemma bisection_is_Cauchy : forall (f : ContinuousFunction) (a b : Q), a < b -> 
  is_Cauchy (bisection_process f a b). 
Proof. 
  intros f a b Hab.
  apply (shrinking_interval_Cauchy (bisection_process f a b) a b Hab).
  intros m n Hmn. apply bisection_shrinks. exact Hab. exact Hmn.
Qed.

(* ===== SECTION 6: SIGN PRESERVATION ===== *)

(* Invariant: f(left) <= 0 and f(right) >= 0 
   This handles the case when f(mid) = 0 (exact root found).
   Note: A strict version (f(left) < 0, f(right) > 0) cannot be proven
   because f(mid) may equal exactly 0 for rational functions. *)
Lemma bisection_preserves_signs_weak : forall (f : ContinuousFunction) (a b : Q) (n : nat), 
  f a <= 0 -> f b >= 0 -> 
  let s := bisection_iter f (mkBisection a b) n in f (bis_left s) <= 0 /\ f (bis_right s) >= 0. 
Proof.
  intros f a b n Hfa Hfb.
  induction n.
  - (* Base case: n = 0 *)
    simpl. split; assumption.
  - (* Inductive step *)
    simpl. destruct IHn as [IHl IHr].
    set (prev := bisection_iter f (mkBisection a b) n) in *.
    unfold bisection_step.
    destruct (Qlt_le_dec (f ((bis_left prev + bis_right prev) / 2)) 0) as [Hmid_neg | Hmid_nonneg].
    + (* f(mid) < 0: new interval is [mid, right] *)
      simpl. split.
      * apply Qlt_le_weak. exact Hmid_neg.
      * exact IHr.
    + (* f(mid) >= 0: new interval is [left, mid] *)
      simpl. split.
      * exact IHl.
      * exact Hmid_nonneg.
Qed.

Theorem IVT_process : forall (f : ContinuousFunction) (a b : Q), 
  a < b -> uniformly_continuous_on f a b -> f a < 0 -> f b > 0 -> 
  exists c : RealProcess, is_Cauchy c /\ in_interval a b c /\ equiv (apply_to_process f c) (fun _ => 0). 
Proof. 
  intros f a b Hab Hcont Hfa Hfb. 
  exists (bisection_process f a b). split; [|split].
  - apply bisection_is_Cauchy. exact Hab.
  - apply bisection_in_interval. apply Qlt_le_weak. exact Hab.
  - (* Show f(bisection_process) -> 0 *)
    unfold equiv, apply_to_process, bisection_process.
    intros eps Heps.
    
    (* Use uniform continuity to get delta *)
    destruct (Hcont eps Heps) as [delta [Hdelta_pos Hdelta_uc]].
    
    (* Use Archimedean to find N such that (b-a)/2^N < delta *)
    assert (Hpos_width : b - a > 0).
    { unfold Qlt, Qminus, Qplus, Qopp in *.
      destruct a as [ap aq]. destruct b as [bp bq].
      simpl in *. nia. }
    destruct (Archimedean_width (b - a) delta Hpos_width Hdelta_pos) as [N HN].
    
    exists N.
    intros n Hn.
    
    (* At step n > N, the interval width is (b-a)/2^n < delta *)
    set (s := bisection_iter f (mkBisection a b) n).
    set (mid := (bis_left s + bis_right s) / 2).
    
    (* Get the sign preservation *)
    pose proof (bisection_preserves_signs_weak f a b n 
                  (Qlt_le_weak _ _ Hfa) (Qlt_le_weak _ _ Hfb)) as [Hleft Hright].
    fold s in Hleft, Hright.
    
    (* Get bounds on interval *)
    pose proof (iter_bounds f a b n (Qlt_le_weak _ _ Hab)) as [Ha_le [Hb_ge Hlr]].
    fold s in Ha_le, Hb_ge, Hlr.
    
    (* Width of interval at step n *)
    pose proof (bisection_width f a b n) as Hwidth.
    fold s in Hwidth.
    
    (* Width < delta for n > N *)
    assert (Hsmall : bis_right s - bis_left s < delta).
    { rewrite Hwidth.
      apply Qle_lt_trans with ((b - a) / Qpow2 N).
      - (* (b-a)/2^n <= (b-a)/2^N because n > N *)
        apply width_shrinks.
        + exact Hpos_width.
        + lia.
      - exact HN. }
    
    (* mid is in interval *)
    assert (Hmid_bounds : a <= mid <= b).
    { unfold mid. split.
      - apply Qle_trans with (bis_left s).
        + exact Ha_le.
        + apply Qle_half_sum_l. exact Hlr.
      - apply Qle_trans with (bis_right s).
        + apply Qle_half_sum_r. exact Hlr.
        + exact Hb_ge. }
    
    (* left is in interval *)
    assert (Hleft_bounds : a <= bis_left s <= b).
    { split. exact Ha_le.
      apply Qle_trans with (bis_right s); [exact Hlr | exact Hb_ge]. }
    
    (* right is in interval *)  
    assert (Hright_bounds : a <= bis_right s <= b).
    { split. apply Qle_trans with (bis_left s); [exact Ha_le | exact Hlr].
      exact Hb_ge. }
    
    (* |mid - left| < delta and |mid - right| < delta *)
    (* Key observation: mid - left = (r-l)/2 and mid - right = -(r-l)/2 *)
    (* Since r - l < delta, we have (r-l)/2 < delta *)
    
    assert (Hhalf_width : (bis_right s - bis_left s) / 2 < delta).
    { apply Qle_lt_trans with (bis_right s - bis_left s).
      - apply half_le_full.
        setoid_replace 0 with (bis_left s - bis_left s) by ring.
        apply Qle_sub_r. exact Hlr.
      - exact Hsmall. }
    
    assert (Hmid_left : Qabs (mid - bis_left s) < delta).
    { unfold mid.
      setoid_replace ((bis_left s + bis_right s) / 2 - bis_left s) 
        with ((bis_right s - bis_left s) / 2) by field.
      rewrite Qabs_pos.
      - exact Hhalf_width.
      - apply Qle_shift_div_l.
        + reflexivity.
        + rewrite Qmult_0_l. 
          setoid_replace 0 with (bis_left s - bis_left s) by ring.
          apply Qle_sub_r. exact Hlr. }
    
    (* By uniform continuity: |f(mid) - f(left)| < eps *)
    assert (Hf_diff : Qabs (f mid - f (bis_left s)) < eps).
    { apply Hdelta_uc.
      - exact Hmid_bounds.
      - exact Hleft_bounds.
      - exact Hmid_left. }
    
    (* Now: f(left) <= 0, so f(mid) < eps *)
    (* And: f(right) >= 0, so f(mid) > -eps *)
    (* Therefore: |f(mid) - 0| < eps *)
    
    (* We need |f(mid) - 0| < eps, which reduces to |f(mid)| < eps *)
    setoid_replace (f mid - 0) with (f mid) by ring.
    
    (* We need |f(mid)| < eps given f(left) <= 0 and |f(mid) - f(left)| < eps *)
    apply Qabs_case.
    + (* f(mid) >= 0: need f(mid) < eps *)
      intro Hfmid_pos.
      (* f(mid) = f(left) + (f(mid) - f(left)) <= f(left) + |f(mid) - f(left)| *)
      (* <= 0 + |f(mid) - f(left)| < eps *)
      apply Qle_lt_trans with (Qabs (f mid - f (bis_left s))).
      * (* f(mid) <= |f(mid) - f(left)| because f(left) <= 0 *)
        (* f(mid) <= f(mid) - f(left) <= |f(mid) - f(left)| *)
        apply Qle_trans with (f mid - f (bis_left s)).
        -- (* f(mid) <= f(mid) - f(left) iff 0 <= -f(left) *)
           rewrite Qle_minus_iff.
           setoid_replace ((f mid - f (bis_left s)) + - f mid) with (- f (bis_left s)) by ring.
           (* 0 <= -f(left) from f(left) <= 0 *)
           pose proof (Qopp_le_compat _ _ Hleft) as H.
           setoid_replace (- (0)) with 0 in H by ring.
           exact H.
        -- apply Qle_Qabs.
      * exact Hf_diff.
    + (* f(mid) < 0: need -f(mid) < eps, i.e., f(mid) > -eps *)
      intro Hfmid_neg.
      (* Similarly using right endpoint *)
      assert (Hrl_nonneg : 0 <= bis_right s - bis_left s).
      { unfold Qle, Qminus, Qplus, Qopp in *. 
        destruct (bis_left s) as [ln ld]. destruct (bis_right s) as [rn rd].
        simpl in *. nia. }
      
      assert (Hmid_right : Qabs (mid - bis_right s) < delta).
      { unfold mid.
        setoid_replace ((bis_left s + bis_right s) / 2 - bis_right s)
          with (-((bis_right s - bis_left s) / 2)) by field.
        rewrite Qabs_opp.
        rewrite Qabs_pos.
        - exact Hhalf_width.
        - apply Qle_shift_div_l.
          + reflexivity.
          + rewrite Qmult_0_l. exact Hrl_nonneg. }
      
      assert (Hf_diff_r : Qabs (f mid - f (bis_right s)) < eps).
      { apply Hdelta_uc.
        - exact Hmid_bounds.
        - exact Hright_bounds.
        - exact Hmid_right. }
      
      (* f(right) >= 0 and |f(mid) - f(right)| < eps *)
      (* So f(mid) > f(right) - eps >= -eps *)
      (* Therefore -f(mid) < eps *)
      
      (* From |f(mid) - f(right)| < eps and f(right) >= 0, show -f(mid) < eps *)
      (* Use nia on the unfolded definitions *)
      apply Qabs_Qlt_condition in Hf_diff_r. destruct Hf_diff_r as [Hlo Hhi].
      unfold Qlt, Qle, Qopp, Qminus, Qplus in *.
      destruct (f mid) as [fmn fmd].
      destruct (f (bis_right s)) as [frn frd].
      destruct eps as [en ed].
      simpl in *. nia.
Qed.

(* ===== SUMMARY ===== *)
Print Assumptions bisection_is_Cauchy.
