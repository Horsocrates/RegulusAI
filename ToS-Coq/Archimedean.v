(* ========================================================================= *)
(*                      ARCHIMEDEAN PROPERTY                                 *)
(*              Powers of 2 eventually exceed any bound                      *)
(*                                                                           *)
(*  Part of: Theory of Systems - Coq Formalization (E/R/R Framework)         *)
(*                                                                           *)
(*  Author:  Horsocrates | Version: 2.0 (E/R/R) | Date: January 2026         *)
(*                                                                           *)
(*  STATUS: 14 Qed, 0 Admitted (100% COMPLETE)                               *)
(*                                                                           *)
(* ========================================================================= *)
(*                                                                           *)
(*  E/R/R INTERPRETATION:                                                    *)
(*  =====================                                                    *)
(*                                                                           *)
(*  Archimedean property is foundational for all analysis:                   *)
(*                                                                           *)
(*    Elements = nat (natural numbers)                                       *)
(*    Roles    = pow2 : nat -> Q (exponential growth)                        *)
(*    Rules    = pow2_unbounded (L5: order + unboundedness)                  *)
(*                                                                           *)
(*  THEOREM: forall eps > 0, exists N, 1/2^N < eps                           *)
(*                                                                           *)
(*  PHILOSOPHICAL NOTE (P4):                                                 *)
(*    This theorem is about PROCESSES - for any precision,                   *)
(*    the process of halving eventually reaches it.                          *)
(*    No completed infinity needed.                                          *)
(*                                                                           *)
(*  AXIOMS: None (derived from Q arithmetic). NO Axiom of Infinity.          *)
(*                                                                           *)
(* ========================================================================= *)

Require Import Coq.QArith.QArith.
Require Import Coq.QArith.Qabs.
Require Import Coq.micromega.Lia.
Require Import Coq.ZArith.ZArith.
Require Import Coq.Arith.PeanoNat.
Require Import Coq.PArith.Pnat.

Open Scope Q_scope.

(* ===== SECTION 1: POWER OF 2 ===== *)

Fixpoint pow2 (n : nat) : positive :=
  match n with O => 1%positive | S n' => (2 * pow2 n')%positive end.

Definition Qpow2 (n : nat) : Q := Z.pos (pow2 n) # 1.

Lemma Qpow2_pos : forall n, 0 < Qpow2 n.
Proof. intro. unfold Qpow2, Qlt. simpl. lia. Qed.

Lemma Qpow2_nonzero : forall n, ~ Qpow2 n == 0.
Proof. intro n. intro H. pose proof (Qpow2_pos n). rewrite H in H0. apply Qlt_irrefl in H0. exact H0. Qed.

Lemma pow2_mono : forall m n, (m <= n)%nat -> (pow2 m <= pow2 n)%positive.
Proof. intros m n Hmn. induction Hmn; simpl; lia. Qed.

Lemma pow2_mono_Z : forall m n, (m <= n)%nat -> (Z.pos (pow2 m) <= Z.pos (pow2 n))%Z.
Proof. intros. apply Pos2Z.pos_le_pos. apply pow2_mono. exact H. Qed.

(* ===== SECTION 2: UNBOUNDEDNESS OF 2^n ===== *)

Lemma pow2_ge_Sn : forall n, (Z.pos (pow2 n) >= Z.of_nat (S n))%Z.
Proof.
  induction n.
  - simpl. lia.
  - simpl pow2.
    replace (Z.pos (2 * pow2 n)) with (2 * Z.pos (pow2 n))%Z by lia.
    replace (Z.of_nat (S (S n))) with (Z.of_nat (S n) + 1)%Z by lia.
    lia.
Qed.

Lemma pow2_exceeds_pos : forall p : positive, exists N : nat, (pow2 N > p)%positive.
Proof.
  intro p.
  exists (Pos.to_nat p).
  pose proof (pow2_ge_Sn (Pos.to_nat p)) as H.
  assert (Hnat : Z.of_nat (S (Pos.to_nat p)) = (Z.pos p + 1)%Z).
  { rewrite Nat2Z.inj_succ. rewrite positive_nat_Z. lia. }
  rewrite Hnat in H. lia.
Qed.

Lemma pow2_unbounded : forall M : Z, exists N : nat, (Z.pos (pow2 N) > M)%Z.
Proof.
  intro M.
  destruct (Z_lt_le_dec M 1) as [Hsmall | Hbig].
  - exists 0%nat. simpl. lia.
  - assert (Hpos : exists p, M = Z.pos p) by (exists (Z.to_pos M); lia).
    destruct Hpos as [p Hp]. subst M.
    destruct (pow2_exceeds_pos p) as [N HN].
    exists N. lia.
Qed.

(* ===== SECTION 3: HELPER LEMMAS FOR ARCHIMEDEAN ===== *)

Lemma Zmult_ge_1 : forall a b : Z, (a >= 1 -> b >= 1 -> a * b >= 1)%Z.
Proof. intros. nia. Qed.

Lemma Zmult_ge_r : forall a c : Z, (a >= 1 -> c > 0 -> a * c >= c)%Z.
Proof. intros. nia. Qed.

(* ===== SECTION 4: ARCHIMEDEAN PROPERTY ===== *)

Theorem Archimedean : forall eps : Q, eps > 0 -> exists N : nat, 1 / Qpow2 N < eps.
Proof.
  intros eps Heps.
  destruct eps as [p q].
  unfold Qlt in Heps. simpl in Heps.
  assert (Hp : (p > 0)%Z) by lia.
  destruct (pow2_exceeds_pos q) as [N HN].
  exists N.
  unfold Qlt, Qdiv, Qmult, Qinv, Qpow2. simpl.
  nia.
Qed.

Theorem Archimedean_width : forall (width eps : Q), width > 0 -> eps > 0 ->
  exists N : nat, width / Qpow2 N < eps.
Proof.
  intros width eps Hwidth Heps.
  destruct width as [wp wq]. destruct eps as [ep eq].
  unfold Qlt in *. simpl in *.
  assert (Hwp : (wp > 0)%Z) by lia.
  assert (Hep : (ep > 0)%Z) by lia.
  destruct (pow2_unbounded (wp * Z.pos eq)%Z) as [N HN].
  exists N.
  unfold Qlt, Qdiv, Qmult, Qinv, Qpow2. simpl.
  (* Goal: wp * Z.pos eq * 1 < ep * (Z.pos wq * Z.pos (pow2 N)) *)
  assert (H1 : (ep >= 1)%Z) by lia.
  assert (H2 : (Z.pos wq >= 1)%Z) by lia.
  assert (Hpow : (Z.pos (pow2 N) > 0)%Z) by lia.
  assert (H3 : (ep * Z.pos wq >= 1)%Z) by (apply Zmult_ge_1; lia).
  assert (H4 : (ep * Z.pos wq * Z.pos (pow2 N) >= Z.pos (pow2 N))%Z) by (apply Zmult_ge_r; lia).
  lia.
Qed.

(* ===== SECTION 5: WIDTH MONOTONICITY ===== *)

Lemma width_shrinks : forall (w : Q) (m n : nat),
  w > 0 -> (m <= n)%nat -> w / Qpow2 n <= w / Qpow2 m.
Proof.
  intros w m n Hw Hmn.
  unfold Qle, Qdiv, Qmult, Qinv, Qpow2. destruct w as [wp wq]. simpl.
  pose proof (pow2_mono_Z m n Hmn).
  unfold Qlt in Hw. simpl in Hw.
  nia.
Qed.

(* ===== SECTION 6: CAUCHY FROM SHRINKING INTERVALS ===== *)

Definition RealProcess := nat -> Q.

Definition is_Cauchy (R : RealProcess) : Prop :=
  forall eps, eps > 0 -> exists N, forall m n, (m > N)%nat -> (n > N)%nat -> Qabs (R m - R n) < eps.

Lemma Qlt_minus_pos : forall a b : Q, a < b -> 0 < b - a.
Proof. intros. unfold Qlt, Qminus, Qplus, Qopp in *. simpl in *. lia. Qed.

Theorem shrinking_interval_Cauchy : forall (R : RealProcess) (a b : Q),
  a < b ->
  (forall m n, (m <= n)%nat -> Qabs (R m - R n) <= (b - a) / Qpow2 m) ->
  is_Cauchy R.
Proof.
  intros R a b Hab Hclose.
  unfold is_Cauchy. intros eps Heps.
  assert (Hba : b - a > 0) by (apply Qlt_minus_pos; exact Hab).
  destruct (Archimedean_width (b - a) eps Hba Heps) as [N HN].
  exists N.
  intros m n Hm Hn.
  destruct (Nat.le_ge_cases m n) as [Hmn | Hnm].
  - apply Qle_lt_trans with ((b - a) / Qpow2 m).
    + apply Hclose. exact Hmn.
    + apply Qle_lt_trans with ((b - a) / Qpow2 N).
      * apply width_shrinks. exact Hba. lia.
      * exact HN.
  - rewrite Qabs_Qminus. apply Qle_lt_trans with ((b - a) / Qpow2 n).
    + apply Hclose. exact Hnm.
    + apply Qle_lt_trans with ((b - a) / Qpow2 N).
      * apply width_shrinks. exact Hba. lia.
      * exact HN.
Qed.

(* ===== VERIFICATION ===== *)

Print Assumptions Archimedean.
Print Assumptions Archimedean_width.
Print Assumptions shrinking_interval_Cauchy.
