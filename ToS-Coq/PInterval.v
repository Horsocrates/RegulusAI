(* ========================================================================= *)
(*  PInterval: Verified Interval Arithmetic                                 *)
(*  Part of: Regulus - Verified AI Computation                              *)
(*                                                                          *)
(*  Author:  Horsocrates | Date: February 2026                              *)
(*                                                                          *)
(*  STATUS: Target - all Qed, 0 Admitted                                    *)
(*                                                                          *)
(* ========================================================================= *)
(*                                                                          *)
(*  E/R/R INTERPRETATION:                                                   *)
(*  =====================                                                   *)
(*                                                                          *)
(*    Elements = Q endpoints (rational bounds)                              *)
(*    Roles    = interval operations (add, sub, mul, relu, ...)             *)
(*    Rules    = correctness: if x in I1, y in I2, then x op y in result    *)
(*                                                                          *)
(*  P4 PHILOSOPHY:                                                          *)
(*    An interval IS the number at the current step of the process          *)
(*    of determination. Not an approximation to a "real" number --          *)
(*    the natural object in finite computation.                             *)
(*                                                                          *)
(*  AXIOMS: NONE. Fully constructive. Extraction-compatible.                *)
(*                                                                          *)
(* ========================================================================= *)

Require Import Coq.QArith.QArith.
Require Import Coq.QArith.Qabs.
Require Import Coq.QArith.Qminmax.
Require Import Coq.micromega.Lia.
Require Import Coq.ZArith.ZArith.
Require Import Coq.Setoids.Setoid.

Open Scope Q_scope.

(* ===== SECTION 1: TYPE DEFINITION ===== *)

Record PInterval := mkPI {
  pi_lo : Q;
  pi_hi : Q;
  pi_valid : pi_lo <= pi_hi
}.

(* Containment predicate *)
Definition pi_contains (I : PInterval) (x : Q) : Prop :=
  pi_lo I <= x /\ x <= pi_hi I.

(* Width *)
Definition pi_width (I : PInterval) : Q :=
  pi_hi I - pi_lo I.

(* Width is non-negative *)
Lemma pi_width_nonneg : forall I : PInterval, 0 <= pi_width I.
Proof.
  intro I. unfold pi_width.
  pose proof (pi_valid I) as Hv.
  setoid_replace 0 with (pi_lo I - pi_lo I) by ring.
  apply Qplus_le_compat.
  - exact Hv.
  - apply Qle_refl.
Qed.

(* ===== SECTION 2: SMART CONSTRUCTORS ===== *)

(* Build interval from a single point *)
Program Definition pi_point (x : Q) : PInterval :=
  mkPI x x _.
Next Obligation. apply Qle_refl. Qed.

(* Build interval with proof obligation *)
Program Definition pi_make (lo hi : Q) (H : lo <= hi) : PInterval :=
  mkPI lo hi H.

(* ===== HELPER: Qle for addition/subtraction ===== *)

Lemma Qplus_le_compat_pair : forall a b c d : Q,
  a <= b -> c <= d -> a + c <= b + d.
Proof. intros. apply Qplus_le_compat; assumption. Qed.

(* Qopp_le_compat from stdlib: forall p q, p <= q -> -q <= -p *)

(* ===== SECTION 3: ADDITION ===== *)
(* [a,b] + [c,d] = [a+c, b+d] *)

Lemma pi_add_valid : forall I J : PInterval,
  pi_lo I + pi_lo J <= pi_hi I + pi_hi J.
Proof.
  intros I J.
  apply Qplus_le_compat; apply pi_valid.
Qed.

Definition pi_add (I J : PInterval) : PInterval :=
  mkPI (pi_lo I + pi_lo J) (pi_hi I + pi_hi J) (pi_add_valid I J).

Theorem pi_add_correct : forall (I J : PInterval) (x y : Q),
  pi_contains I x -> pi_contains J y -> pi_contains (pi_add I J) (x + y).
Proof.
  intros I J x y [HIl HIr] [HJl HJr].
  unfold pi_contains, pi_add. simpl.
  split; apply Qplus_le_compat; assumption.
Qed.

(* ===== SECTION 4: NEGATION ===== *)
(* -[a,b] = [-b, -a] *)

Lemma pi_neg_valid : forall I : PInterval,
  -(pi_hi I) <= -(pi_lo I).
Proof. intro I. apply Qopp_le_compat. apply pi_valid. Qed.

Definition pi_neg (I : PInterval) : PInterval :=
  mkPI (-(pi_hi I)) (-(pi_lo I)) (pi_neg_valid I).

Theorem pi_neg_correct : forall (I : PInterval) (x : Q),
  pi_contains I x -> pi_contains (pi_neg I) (-x).
Proof.
  intros I x [Hl Hr].
  unfold pi_contains, pi_neg. simpl.
  split; apply Qopp_le_compat; assumption.
Qed.

(* ===== SECTION 5: SUBTRACTION ===== *)
(* [a,b] - [c,d] = [a-d, b-c] *)

Lemma pi_sub_valid : forall I J : PInterval,
  pi_lo I - pi_hi J <= pi_hi I - pi_lo J.
Proof.
  intros I J.
  unfold Qminus.
  apply Qplus_le_compat.
  - apply pi_valid.
  - apply Qopp_le_compat. apply pi_valid.
Qed.

Definition pi_sub (I J : PInterval) : PInterval :=
  mkPI (pi_lo I - pi_hi J) (pi_hi I - pi_lo J) (pi_sub_valid I J).

Theorem pi_sub_correct : forall (I J : PInterval) (x y : Q),
  pi_contains I x -> pi_contains J y -> pi_contains (pi_sub I J) (x - y).
Proof.
  intros I J x y [HIl HIr] [HJl HJr].
  unfold pi_contains, pi_sub, Qminus. simpl.
  split; apply Qplus_le_compat; try assumption; apply Qopp_le_compat; assumption.
Qed.

(* ===== SECTION 6: SCALAR MULTIPLICATION ===== *)
(* k * [a,b] = [k*a, k*b] if k >= 0, [k*b, k*a] if k < 0 *)

Lemma Qmult_le_l : forall k a b : Q, 0 <= k -> a <= b -> k * a <= k * b.
Proof.
  intros k a b Hk Hab.
  setoid_replace (k * a) with (a * k) by ring.
  setoid_replace (k * b) with (b * k) by ring.
  apply Qmult_le_compat_r; assumption.
Qed.

Lemma pi_scale_nonneg_valid : forall (k : Q) (I : PInterval),
  0 <= k -> k * pi_lo I <= k * pi_hi I.
Proof.
  intros k I Hk. apply Qmult_le_l; [exact Hk | apply pi_valid].
Qed.

Definition pi_scale_nonneg (k : Q) (I : PInterval) (Hk : 0 <= k) : PInterval :=
  mkPI (k * pi_lo I) (k * pi_hi I) (pi_scale_nonneg_valid k I Hk).

Theorem pi_scale_nonneg_correct : forall (k : Q) (I : PInterval) (Hk : 0 <= k) (x : Q),
  pi_contains I x -> pi_contains (pi_scale_nonneg k I Hk) (k * x).
Proof.
  intros k I Hk x [Hl Hr].
  unfold pi_contains. simpl.
  split; apply Qmult_le_l; assumption.
Qed.

(* ===== SECTION 7: MULTIPLICATION (full) ===== *)
(* [a,b] * [c,d] = [min(ac,ad,bc,bd), max(ac,ad,bc,bd)] *)

Definition q_min4 (a b c d : Q) : Q := Qmin (Qmin a b) (Qmin c d).
Definition q_max4 (a b c d : Q) : Q := Qmax (Qmax a b) (Qmax c d).

Lemma q_min4_le : forall a b c d x : Q,
  (x == a \/ x == b \/ x == c \/ x == d) -> q_min4 a b c d <= x.
Proof.
  intros a b c d x Hx.
  unfold q_min4.
  destruct Hx as [Ha | [Hb | [Hc | Hd]]]; rewrite Ha || rewrite Hb || rewrite Hc || rewrite Hd.
  - apply Qle_trans with (Qmin a b). apply Q.le_min_l. apply Q.le_min_l.
  - apply Qle_trans with (Qmin a b). apply Q.le_min_l. apply Q.le_min_r.
  - apply Qle_trans with (Qmin c d). apply Q.le_min_r. apply Q.le_min_l.
  - apply Qle_trans with (Qmin c d). apply Q.le_min_r. apply Q.le_min_r.
Qed.

Lemma q_max4_ge : forall a b c d x : Q,
  (x == a \/ x == b \/ x == c \/ x == d) -> x <= q_max4 a b c d.
Proof.
  intros a b c d x Hx.
  unfold q_max4.
  destruct Hx as [Ha | [Hb | [Hc | Hd]]]; rewrite Ha || rewrite Hb || rewrite Hc || rewrite Hd.
  - apply Qle_trans with (Qmax a b). apply Q.le_max_l. apply Q.le_max_l.
  - apply Qle_trans with (Qmax a b). apply Q.le_max_r. apply Q.le_max_l.
  - apply Qle_trans with (Qmax c d). apply Q.le_max_l. apply Q.le_max_r.
  - apply Qle_trans with (Qmax c d). apply Q.le_max_r. apply Q.le_max_r.
Qed.

Lemma q_min4_le_max4 : forall a b c d : Q,
  q_min4 a b c d <= q_max4 a b c d.
Proof.
  intros.
  apply Qle_trans with a.
  - apply q_min4_le. left. apply Qeq_refl.
  - apply q_max4_ge. left. apply Qeq_refl.
Qed.

Definition pi_mul (I J : PInterval) : PInterval :=
  let ac := pi_lo I * pi_lo J in
  let ad := pi_lo I * pi_hi J in
  let bc := pi_hi I * pi_lo J in
  let bd := pi_hi I * pi_hi J in
  mkPI (q_min4 ac ad bc bd) (q_max4 ac ad bc bd)
       (q_min4_le_max4 ac ad bc bd).

(* === Monotonicity helpers for multiplication === *)

Lemma Qmult_le_r_neg : forall x y z : Q, x <= y -> z <= 0 -> y * z <= x * z.
Proof.
  intros x y z Hxy Hz.
  setoid_replace (y * z) with (-(y * (-z))) by ring.
  setoid_replace (x * z) with (-(x * (-z))) by ring.
  apply Qopp_le_compat. apply Qmult_le_compat_r.
  exact Hxy.
  setoid_replace 0 with (-0) by ring. apply Qopp_le_compat. exact Hz.
Qed.

Lemma Qmin_le_both : forall a b x : Q, a <= x \/ b <= x -> Qmin a b <= x.
Proof.
  intros a b x [H | H].
  - apply Qle_trans with a. apply Q.le_min_l. exact H.
  - apply Qle_trans with b. apply Q.le_min_r. exact H.
Qed.

Lemma Qmax_ge_both : forall a b x : Q, x <= a \/ x <= b -> x <= Qmax a b.
Proof.
  intros a b x [H | H].
  - apply Qle_trans with a. exact H. apply Q.le_max_l.
  - apply Qle_trans with b. exact H. apply Q.le_max_r.
Qed.

Lemma Qmult_between_r : forall a b z x : Q,
  a <= x -> x <= b ->
  Qmin (a * z) (b * z) <= x * z /\ x * z <= Qmax (a * z) (b * z).
Proof.
  intros a b z x Hax Hxb.
  destruct (Qlt_le_dec z 0) as [Hz_neg | Hz_nonneg].
  - split.
    + apply Qmin_le_both. right.
      apply Qmult_le_r_neg; [exact Hxb | apply Qlt_le_weak; exact Hz_neg].
    + apply Qmax_ge_both. left.
      apply Qmult_le_r_neg; [exact Hax | apply Qlt_le_weak; exact Hz_neg].
  - split.
    + apply Qmin_le_both. left. apply Qmult_le_compat_r; assumption.
    + apply Qmax_ge_both. right. apply Qmult_le_compat_r; assumption.
Qed.

Lemma Qmult_between_l : forall c d z y : Q,
  c <= y -> y <= d ->
  Qmin (z * c) (z * d) <= z * y /\ z * y <= Qmax (z * c) (z * d).
Proof.
  intros c d z y Hcy Hyd.
  setoid_rewrite Qmult_comm.
  apply Qmult_between_r; assumption.
Qed.

Lemma Qmin_le_min : forall a b c d : Q,
  a <= c -> b <= d -> Qmin a b <= Qmin c d.
Proof.
  intros a b c d Hac Hbd.
  apply Q.min_glb.
  - apply Qle_trans with a. apply Q.le_min_l. exact Hac.
  - apply Qle_trans with b. apply Q.le_min_r. exact Hbd.
Qed.

Lemma Qmax_le_max : forall a b c d : Q,
  a <= c -> b <= d -> Qmax a b <= Qmax c d.
Proof.
  intros a b c d Hac Hbd.
  apply Q.max_lub.
  - apply Qle_trans with c. exact Hac. apply Q.le_max_l.
  - apply Qle_trans with d. exact Hbd. apply Q.le_max_r.
Qed.

(* Helper for multiplication correctness *)
(* Two-step monotonicity: first fix y, bound x*y by a*y..b*y, *)
(* then bound a*y and b*y by products of endpoints. *)
Lemma Qmult_le_compat_between : forall a b c d x y : Q,
  a <= x -> x <= b -> c <= y -> y <= d ->
  q_min4 (a*c) (a*d) (b*c) (b*d) <= x * y /\
  x * y <= q_max4 (a*c) (a*d) (b*c) (b*d).
Proof.
  intros a b c d x y Hax Hxb Hcy Hyd.
  unfold q_min4, q_max4.
  destruct (Qmult_between_r a b y x Hax Hxb) as [Hmin_xy Hmax_xy].
  destruct (Qmult_between_l c d a y Hcy Hyd) as [Hmin_ay Hmax_ay].
  destruct (Qmult_between_l c d b y Hcy Hyd) as [Hmin_by Hmax_by].
  split.
  - apply Qle_trans with (Qmin (a * y) (b * y)).
    + apply Qmin_le_min; assumption.
    + exact Hmin_xy.
  - apply Qle_trans with (Qmax (a * y) (b * y)).
    + exact Hmax_xy.
    + apply Qmax_le_max; assumption.
Qed.

Theorem pi_mul_correct : forall (I J : PInterval) (x y : Q),
  pi_contains I x -> pi_contains J y -> pi_contains (pi_mul I J) (x * y).
Proof.
  intros I J x y HI HJ.
  destruct HI as [HIl HIr]. destruct HJ as [HJl HJr].
  unfold pi_contains, pi_mul. simpl.
  apply Qmult_le_compat_between; assumption.
Qed.

(* ===== SECTION 8: ReLU ===== *)
(* relu([a,b]) = [max(0,a), max(0,b)] *)

Lemma pi_relu_valid : forall I : PInterval,
  Qmax 0 (pi_lo I) <= Qmax 0 (pi_hi I).
Proof.
  intro I.
  pose proof (pi_valid I) as Hv.
  destruct (Qlt_le_dec (pi_lo I) 0) as [Hlo_neg | Hlo_nonneg];
  destruct (Qlt_le_dec (pi_hi I) 0) as [Hhi_neg | Hhi_nonneg].
  - rewrite Q.max_l by (apply Qlt_le_weak; assumption).
    rewrite Q.max_l by (apply Qlt_le_weak; assumption).
    apply Qle_refl.
  - rewrite Q.max_l by (apply Qlt_le_weak; assumption).
    rewrite Q.max_r by assumption.
    assumption.
  - exfalso. apply (Qlt_not_le _ _ Hhi_neg).
    apply Qle_trans with (pi_lo I); assumption.
  - rewrite Q.max_r by assumption.
    rewrite Q.max_r by assumption.
    assumption.
Qed.

Definition pi_relu (I : PInterval) : PInterval :=
  mkPI (Qmax 0 (pi_lo I)) (Qmax 0 (pi_hi I)) (pi_relu_valid I).

Theorem pi_relu_correct : forall (I : PInterval) (x : Q),
  pi_contains I x -> pi_contains (pi_relu I) (Qmax 0 x).
Proof.
  intros I x [Hl Hr].
  unfold pi_contains, pi_relu. simpl.
  split; apply Q.max_le_compat; try apply Qle_refl; assumption.
Qed.

(* ===== SECTION 9: ABSOLUTE VALUE ===== *)

Definition pi_abs (I : PInterval) : PInterval.
Proof.
  refine (mkPI
    (if Qlt_le_dec (pi_hi I) 0 then -(pi_hi I)
     else if Qlt_le_dec 0 (pi_lo I) then pi_lo I
     else 0)
    (Qmax (-(pi_lo I)) (pi_hi I))
    _).
  destruct (Qlt_le_dec (pi_hi I) 0) as [Hhi_neg | Hhi_nonneg].
  - apply Qle_trans with (-(pi_lo I)).
    + apply Qopp_le_compat. apply pi_valid.
    + apply Q.le_max_l.
  - destruct (Qlt_le_dec 0 (pi_lo I)) as [Hlo_pos | Hlo_nonpos].
    + apply Qle_trans with (pi_hi I).
      * exact (pi_valid I).
      * apply Q.le_max_r.
    + apply Qle_trans with 0.
      * apply Qle_refl.
      * destruct (Q.max_spec (-(pi_lo I)) (pi_hi I)) as [[_ Hm] | [_ Hm]];
        rewrite Hm.
        -- exact Hhi_nonneg.
        -- pose proof (Qopp_le_compat _ _ Hlo_nonpos) as H.
           setoid_replace (- 0) with 0 in H by ring. exact H.
Defined.

Theorem pi_abs_correct : forall (I : PInterval) (x : Q),
  pi_contains I x -> pi_contains (pi_abs I) (Qabs x).
Proof.
  intros I x [Hl Hr].
  unfold pi_contains, pi_abs. simpl.
  destruct (Qlt_le_dec (pi_hi I) 0) as [Hhi_neg | Hhi_nonneg].
  - assert (Hx_neg : x < 0) by (apply Qle_lt_trans with (pi_hi I); assumption).
    rewrite Qabs_neg by (apply Qlt_le_weak; assumption).
    split.
    + apply Qopp_le_compat. assumption.
    + apply Qle_trans with (-(pi_lo I)).
      * apply Qopp_le_compat. assumption.
      * apply Q.le_max_l.
  - destruct (Qlt_le_dec 0 (pi_lo I)) as [Hlo_pos | Hlo_nonpos].
    + assert (Hx_pos : 0 < x) by (apply Qlt_le_trans with (pi_lo I); assumption).
      rewrite Qabs_pos by (apply Qlt_le_weak; assumption).
      split.
      * assumption.
      * apply Qle_trans with (pi_hi I). assumption. apply Q.le_max_r.
    + apply Qabs_case; intro Hx_sign.
      * split.
        -- assumption.
        -- apply Qle_trans with (pi_hi I). assumption. apply Q.le_max_r.
      * split.
        -- pose proof (Qopp_le_compat _ _ Hx_sign) as H.
           setoid_replace (- 0) with 0 in H by ring. exact H.
        -- apply Qle_trans with (-(pi_lo I)).
           ++ apply Qopp_le_compat. assumption.
           ++ apply Q.le_max_l.
Qed.

(* ===== SECTION 10: OVERLAP ===== *)

Definition pi_overlaps (I J : PInterval) : bool :=
  if Qlt_le_dec (pi_hi I) (pi_lo J) then false
  else if Qlt_le_dec (pi_hi J) (pi_lo I) then false
  else true.

Lemma pi_overlaps_sound : forall I J : PInterval,
  pi_overlaps I J = false ->
  ~ exists x, pi_contains I x /\ pi_contains J x.
Proof.
  intros I J Hf [x [[Hxl Hxh] [Hyl Hyh]]].
  unfold pi_overlaps in Hf.
  destruct (Qlt_le_dec (pi_hi I) (pi_lo J)) as [H1 | H1].
  - apply (Qlt_not_le _ _ H1). apply Qle_trans with x; assumption.
  - destruct (Qlt_le_dec (pi_hi J) (pi_lo I)) as [H2 | H2].
    + apply (Qlt_not_le _ _ H2). apply Qle_trans with x; assumption.
    + discriminate.
Qed.

(* ===== SECTION 11: DEFINITIONS FOR EXTRACTION ===== *)

Definition pi_nonzero (I : PInterval) : Prop :=
  pi_lo I > 0 \/ pi_hi I < 0.

Definition pi_nonzero_dec (I : PInterval) : bool :=
  if Qlt_le_dec 0 (pi_lo I) then true
  else if Qlt_le_dec (pi_hi I) 0 then true
  else false.

(* ===== SECTION 12: DIVISION ===== *)
(* [a,b] / [c,d] where 0 ∉ [c,d] *)
(* Strategy: compute reciprocal interval, then multiply *)

(* Helper: Qinv preserves sign *)
Lemma Qinv_pos : forall q : Q, 0 < q -> 0 < / q.
Proof.
  intros q Hq.
  destruct (Qlt_le_dec 0 (/ q)) as [H | H].
  - exact H.
  - exfalso.
    assert (Hinv : / q <= 0) by exact H.
    assert (Hprod : / q * q <= 0 * q).
    { apply Qmult_le_compat_r; [exact Hinv | apply Qlt_le_weak; exact Hq]. }
    setoid_replace (0 * q) with 0 in Hprod by ring.
    setoid_replace (/ q * q) with (q * / q) in Hprod by ring.
    rewrite Qmult_inv_r in Hprod.
    + apply (Qlt_not_le 0 1). reflexivity. exact Hprod.
    + intro Heq. rewrite Heq in Hq. apply (Qlt_irrefl 0). exact Hq.
Qed.

Lemma Qinv_neg : forall q : Q, q < 0 -> / q < 0.
Proof.
  intros q Hq.
  assert (Hq_neq : ~ q == 0).
  { intro Heq. rewrite Heq in Hq. apply (Qlt_irrefl 0). exact Hq. }
  assert (Hnq_pos : 0 < -q).
  { setoid_replace 0 with (-0) by ring. apply Qopp_lt_compat. exact Hq. }
  pose proof (Qinv_pos (-q) Hnq_pos) as Hinv_nq.
  (* /(-q) = -(/q), so 0 < -(/q), hence /q < 0 *)
  assert (Heq_inv : / (-q) == - / q).
  { field. exact Hq_neq. }
  rewrite Heq_inv in Hinv_nq.
  setoid_replace 0 with (- 0) in Hinv_nq by ring.
  apply Qopp_lt_compat in Hinv_nq.
  setoid_replace (- - / q) with (/ q) in Hinv_nq by ring.
  setoid_replace (- - 0) with 0 in Hinv_nq by ring.
  exact Hinv_nq.
Qed.

Lemma Qinv_le_compat : forall a b : Q,
  0 < a -> a <= b -> / b <= / a.
Proof.
  intros a b Ha Hab.
  assert (Hb : 0 < b) by (apply Qlt_le_trans with a; assumption).
  assert (Ha_inv : 0 < / a) by (apply Qinv_pos; exact Ha).
  assert (Hb_inv : 0 < / b) by (apply Qinv_pos; exact Hb).
  assert (Ha_neq : ~ a == 0).
  { intro Heq. rewrite Heq in Ha. apply (Qlt_irrefl 0). exact Ha. }
  assert (Hb_neq : ~ b == 0).
  { intro Heq. rewrite Heq in Hb. apply (Qlt_irrefl 0). exact Hb. }
  (* /b <= /a iff /b * a * b <= /a * a * b iff a <= b *)
  apply Qmult_le_r with a. exact Ha.
  setoid_replace (/ b * a) with (a * / b) by ring.
  setoid_replace (/ a * a) with 1 by (field; exact Ha_neq).
  apply Qmult_le_r with b. exact Hb.
  setoid_replace (a * / b * b) with a by (field; exact Hb_neq).
  setoid_replace (1 * b) with b by ring.
  exact Hab.
Qed.

Lemma Qinv_le_compat_neg : forall a b : Q,
  b < 0 -> a <= b -> / b <= / a.
Proof.
  intros a b Hb Hab.
  assert (Ha : a < 0) by (apply Qle_lt_trans with b; assumption).
  (* Use: /a = -/(-a) and similarly for b, then use positive case *)
  assert (H0a : 0 < -a).
  { setoid_replace 0 with (-0) by ring. apply Qopp_lt_compat. exact Ha. }
  assert (H0b : 0 < -b).
  { setoid_replace 0 with (-0) by ring. apply Qopp_lt_compat. exact Hb. }
  assert (Hneg : -b <= -a) by (apply Qopp_le_compat; exact Hab).
  pose proof (Qinv_le_compat (-b) (-a) H0b Hneg) as Hle.
  assert (Ha_neq : ~ a == 0).
  { intro Heq. rewrite Heq in Ha. apply (Qlt_irrefl 0). exact Ha. }
  assert (Hb_neq : ~ b == 0).
  { intro Heq. rewrite Heq in Hb. apply (Qlt_irrefl 0). exact Hb. }
  setoid_replace (/ (-a)) with (- / a) in Hle by (field; exact Ha_neq).
  setoid_replace (/ (-b)) with (- / b) in Hle by (field; exact Hb_neq).
  apply Qopp_le_compat in Hle.
  setoid_replace (- - / a) with (/ a) in Hle by ring.
  setoid_replace (- - / b) with (/ b) in Hle by ring.
  exact Hle.
Qed.

(* Reciprocal of positive interval: 0 < c <= d -> [1/d, 1/c] *)
Lemma pi_inv_pos_valid : forall (I : PInterval),
  0 < pi_lo I -> / (pi_hi I) <= / (pi_lo I).
Proof.
  intros I Hlo.
  apply Qinv_le_compat. exact Hlo. apply pi_valid.
Qed.

(* Reciprocal of negative interval: c <= d < 0 -> [1/d, 1/c] *)
Lemma pi_inv_neg_valid : forall (I : PInterval),
  pi_hi I < 0 -> / (pi_hi I) <= / (pi_lo I).
Proof.
  intros I Hhi.
  apply Qinv_le_compat_neg. exact Hhi. apply pi_valid.
Qed.

(* Division: we define it for both cases using pi_nonzero *)
Definition pi_div (I J : PInterval) (HJ : pi_nonzero J) : PInterval :=
  let inv_lo := / (pi_hi J) in
  let inv_hi := / (pi_lo J) in
  let ac := pi_lo I * inv_lo in
  let ad := pi_lo I * inv_hi in
  let bc := pi_hi I * inv_lo in
  let bd := pi_hi I * inv_hi in
  mkPI (q_min4 ac ad bc bd) (q_max4 ac ad bc bd)
       (q_min4_le_max4 ac ad bc bd).

(* Correctness: x ∈ I, y ∈ J, 0 ∉ J -> x/y ∈ pi_div I J *)
Lemma Qinv_between : forall c d y : Q,
  0 < c -> c <= y -> y <= d ->
  / d <= / y /\ / y <= / c.
Proof.
  intros c d y Hc Hcy Hyd.
  assert (Hy_pos : 0 < y) by (apply Qlt_le_trans with c; assumption).
  split.
  - apply Qinv_le_compat. exact Hy_pos. exact Hyd.
  - apply Qinv_le_compat. exact Hc. exact Hcy.
Qed.

Lemma Qinv_between_neg : forall c d y : Q,
  d < 0 -> c <= y -> y <= d ->
  / d <= / y /\ / y <= / c.
Proof.
  intros c d y Hd Hcy Hyd.
  assert (Hy_neg : y < 0) by (apply Qle_lt_trans with d; exact Hyd || exact Hd).
  assert (Hc_neg : c < 0) by (apply Qle_lt_trans with d; [exact (Qle_trans _ _ _ Hcy Hyd) | exact Hd]).
  split.
  - apply Qinv_le_compat_neg. exact Hd. exact Hyd.
  - apply Qinv_le_compat_neg. exact Hy_neg. exact Hcy.
Qed.

Theorem pi_div_correct : forall (I J : PInterval) (HJ : pi_nonzero J) (x y : Q),
  pi_contains I x -> pi_contains J y -> ~ y == 0 ->
  pi_contains (pi_div I J HJ) (x * / y).
Proof.
  intros I J HJ x y [HIl HIr] [HJl HJr] Hy_neq.
  unfold pi_contains, pi_div. simpl.
  apply Qmult_le_compat_between.
  - exact HIl.
  - exact HIr.
  - destruct HJ as [Hpos | Hneg].
    + destruct (Qinv_between _ _ y Hpos HJl HJr) as [H _]. exact H.
    + destruct (Qinv_between_neg _ _ y Hneg HJl HJr) as [H _]. exact H.
  - destruct HJ as [Hpos | Hneg].
    + destruct (Qinv_between _ _ y Hpos HJl HJr) as [_ H]. exact H.
    + destruct (Qinv_between_neg _ _ y Hneg HJl HJr) as [_ H]. exact H.
Qed.

(* ===== SECTION 13: MONOTONE FUNCTION LIFTING ===== *)
(* For any monotone increasing f : Q -> Q, f([a,b]) = [f(a), f(b)] *)
(* This covers sigmoid, tanh, and any other monotone activation. *)

Definition monotone_increasing (f : Q -> Q) : Prop :=
  forall x y : Q, x <= y -> f x <= f y.

Lemma pi_monotone_valid : forall (f : Q -> Q) (I : PInterval),
  monotone_increasing f -> f (pi_lo I) <= f (pi_hi I).
Proof.
  intros f I Hmon. apply Hmon. apply pi_valid.
Qed.

Definition pi_monotone (f : Q -> Q) (I : PInterval)
  (Hmon : monotone_increasing f) : PInterval :=
  mkPI (f (pi_lo I)) (f (pi_hi I)) (pi_monotone_valid f I Hmon).

Theorem pi_monotone_correct : forall (f : Q -> Q) (I : PInterval)
  (Hmon : monotone_increasing f) (x : Q),
  pi_contains I x -> pi_contains (pi_monotone f I Hmon) (f x).
Proof.
  intros f I Hmon x [Hl Hr].
  unfold pi_contains, pi_monotone. simpl.
  split; apply Hmon; assumption.
Qed.

(* Decreasing version — for completeness *)
Definition monotone_decreasing (f : Q -> Q) : Prop :=
  forall x y : Q, x <= y -> f y <= f x.

Lemma pi_antitone_valid : forall (f : Q -> Q) (I : PInterval),
  monotone_decreasing f -> f (pi_hi I) <= f (pi_lo I).
Proof.
  intros f I Hmon. apply Hmon. apply pi_valid.
Qed.

Definition pi_antitone (f : Q -> Q) (I : PInterval)
  (Hmon : monotone_decreasing f) : PInterval :=
  mkPI (f (pi_hi I)) (f (pi_lo I)) (pi_antitone_valid f I Hmon).

Theorem pi_antitone_correct : forall (f : Q -> Q) (I : PInterval)
  (Hmon : monotone_decreasing f) (x : Q),
  pi_contains I x -> pi_contains (pi_antitone f I Hmon) (f x).
Proof.
  intros f I Hmon x [Hl Hr].
  unfold pi_contains, pi_antitone. simpl.
  split; apply Hmon; assumption.
Qed.

(* ===== SECTION 14: DOT PRODUCT / MATMUL BUILDING BLOCKS ===== *)
(* Matrix-vector multiply is just: sum of (scalar * interval) *)
(* We already have pi_add and pi_mul. For matmul we need *)
(* a fold over lists. Define sum of intervals. *)

Require Import Coq.Lists.List.
Import ListNotations.

Fixpoint pi_sum (xs : list PInterval) : PInterval :=
  match xs with
  | [] => pi_point 0
  | x :: rest => pi_add x (pi_sum rest)
  end.

Theorem pi_sum_correct : forall (xs : list PInterval) (vals : list Q),
  length xs = length vals ->
  Forall2 pi_contains xs vals ->
  pi_contains (pi_sum xs) (fold_right Qplus 0 vals).
Proof.
  intros xs vals Hlen HF2.
  induction HF2 as [| I v rest vrest HI HF2' IH].
  - simpl. unfold pi_contains, pi_point. simpl. split; apply Qle_refl.
  - simpl. apply pi_add_correct.
    + exact HI.
    + apply IH. simpl in Hlen. lia.
Qed.

(* Dot product: given list of intervals and list of scalar intervals *)
Fixpoint pi_dot (ws vs : list PInterval) : PInterval :=
  match ws, vs with
  | [], _ => pi_point 0
  | _, [] => pi_point 0
  | w :: ws', v :: vs' => pi_add (pi_mul w v) (pi_dot ws' vs')
  end.

Theorem pi_dot_correct :
  forall (ws vs : list PInterval) (wvals vvals : list Q),
  Forall2 pi_contains ws wvals ->
  Forall2 pi_contains vs vvals ->
  length ws = length vs ->
  pi_contains (pi_dot ws vs)
    (fold_right Qplus 0 (map (fun p => fst p * snd p) (combine wvals vvals))).
Proof.
  intros ws vs wvals vvals HFw HFv Hlen.
  generalize dependent vvals. generalize dependent vs.
  induction HFw as [| Iw wval wrest wvrest HIw HFw' IH].
  - intros. simpl. unfold pi_contains, pi_point. simpl. split; apply Qle_refl.
  - intros [| Iv vrest] Hlen vvals HFv.
    + simpl in Hlen. discriminate.
    + inversion HFv as [| Iv' vval vrest' vvrest HIv HFv' Heq1 Heq2]. subst.
      simpl. apply pi_add_correct.
      * apply pi_mul_correct; assumption.
      * apply IH.
        -- simpl in Hlen. injection Hlen as Hlen. exact Hlen.
        -- exact HFv'.
Qed.

(* ===== VERIFICATION ===== *)
Print Assumptions pi_add_correct.
Print Assumptions pi_sub_correct.
Print Assumptions pi_neg_correct.
Print Assumptions pi_mul_correct.
Print Assumptions pi_relu_correct.
Print Assumptions pi_abs_correct.
Print Assumptions pi_div_correct.
Print Assumptions pi_monotone_correct.
Print Assumptions pi_antitone_correct.
Print Assumptions pi_sum_correct.
Print Assumptions pi_dot_correct.
