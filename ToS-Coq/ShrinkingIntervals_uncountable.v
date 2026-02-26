(* ========================================================================= *)
(*                      SHRINKING INTERVALS THEORY                          *)
(*                                                                          *)
(*  INTEGRATION WITH THEORY OF SYSTEMS CORE (E/R/R Framework)               *)
(*  =========================================================               *)
(*                                                                          *)
(*  This file provides the unified theory of shrinking intervals that       *)
(*  underlies IVT, EVT, and the diagonal argument.                          *)
(*                                                                          *)
(*  STATUS: 167 Qed, 0 Admitted (100% COMPLETE)                             *)
(*                                                                          *)
(* ========================================================================= *)
(*                                                                          *)
(*  E/R/R INTERPRETATION (from TheoryOfSystems_Core_ERR.v):                 *)
(*                                                                          *)
(*  This file implements FunctionalSystem L2 (RealProcess level):           *)
(*                                                                          *)
(*    Elements = CauchyProcess (Products of L1)                             *)
(*    Roles    = cauchy_equiv (equivalence of processes)                    *)
(*    Rules    = is_Cauchy (Constitution for convergence)                   *)
(*                                                                          *)
(*  The uncountability theorem operates at L3:                              *)
(*                                                                          *)
(*    Elements(L3) = Enumeration = nat -> CauchyProcess                     *)
(*    Products(L3) = Diagonal D (constructed to differ from all E(n))       *)
(*                                                                          *)
(*  ACTUALIZATION (P4):                                                     *)
(*    Process (nat -> Q)  --[is_Cauchy]-->  CauchyProcess (Product)         *)
(*    Products(L2) = Elements(L3)                                           *)
(*                                                                          *)
(* ========================================================================= *)
(*                                                                          *)
(*  PHILOSOPHICAL FOUNDATION (from Theory of Systems):                      *)
(*                                                                          *)
(*  P4 (Principle of Finitude): At any moment, a system contains finitely   *)
(*      many elements. Infinity is a property of PROCESS, not object.       *)
(*                                                                          *)
(*  L4 (Law of Sufficient Reason): Every distinction requires GROUND.       *)
(*      -> trisect_step (n+1) <> trisect_step (n) BECAUSE:                  *)
(*        1. Interval width at (n+1) = width(n) / 3                         *)
(*        2. Precision criterion CHANGES: 1/3^(n+1) < 1/3^n                 *)
(*        3. This is the SUFFICIENT REASON for the step                     *)
(*                                                                          *)
(*  L5 (Law of Order): Every element has unique POSITION.                   *)
(*      -> Each R(n) occupies position n in the sequence                    *)
(*      -> n <> m implies R(n) distinguishable from R(m)                    *)
(*                                                                          *)
(*  CONSEQUENCE FOR REAL NUMBERS:                                           *)
(*  - A real number is not an infinite decimal, but a PROCESS that          *)
(*    generates increasingly precise rational approximations.               *)
(*  - Convergence means: for any precision eps, the process eventually      *)
(*    produces approximations within eps of each other.                     *)
(*  - This is exactly what shrinking intervals provide: at step n,          *)
(*    the interval width is finite, and the sequence of widths              *)
(*    converges to zero AS A PROCESS.                                       *)
(*                                                                          *)
(*  KEY THEOREM (L4 + Trisection):                                          *)
(*  Each trisection step has SUFFICIENT REASON to differ from previous:     *)
(*                                                                          *)
(*    trisect_productive : forall s, valid s -> trisect_step s <> s         *)
(*                                                                          *)
(*  Author: Horsocrates | Version: 3.0 (E/R/R) | Date: January 2026         *)
(* ========================================================================= *)

Require Import Coq.QArith.QArith.
Require Import Coq.QArith.Qabs.
Require Import Coq.QArith.Qfield.
Require Import Coq.micromega.Lia.
Require Import Coq.ZArith.ZArith.
Require Import Coq.Arith.PeanoNat.
Require Import Coq.PArith.Pnat.
Require Import Coq.Logic.Classical.

(** 
 PHILOSOPHICAL NOTE ON CLASSICAL LOGIC:
 
 The use of Classical logic (excluded middle) aligns with the Theory of Systems
 where L3 (Law of Excluded Middle) is a fundamental law: for any proposition A,
 either A or ~A holds. This is not a limitation but a structural property of
 distinction itself - the primordial A vs ~A that grounds all reasoning.
 
 In this proof, classical logic is used to resolve limit-based arguments
 where we need to show L_D deg L_n (the diagonal limit differs from each E_n's limit).
*)

Open Scope Q_scope.

(* ========================================================================= *)
(* INHERITANCE MODULE: REALPROCESS AS STRUCTUREDPROCESS *)
(* ========================================================================= *)

(**
 FORMAL CORRESPONDENCE TABLE
 ===========================
 
 | TheoryOfSystems_Core | ShrinkingIntervals | Law |
 |--------------------------|---------------------------|----------|
 | Level L2 | "Real Numbers" level | P1 |
 | Position (nat) | Index n in sequence | L5 |
 | ss_assignment n | R(n) : Q | L5 |
 | ss_L5_valid | Function uniqueness | L5 |
 | ProductiveGenerator | TrisectGenerator | P4 |
 | pgen_seed | initial_state [0,1] | P4 |
 | pgen_step | trisect_avoiding E n | P4 |
 | pgen_productive | trisect_shrinks | L4+P4 |
 | Difference_Exists | diagonal deg E(n) at pos n | L4 |
 
 INTERPRETATION:
 
 A RealProcess R is a StructuredSystem L2 where:
 - crit_domain = Q (rational numbers)
 - crit_predicate = is_Cauchy (convergence criterion)
 - ss_assignment n = Some (R n)
 - ss_L5_valid follows from R being a FUNCTION (injective on positions)
 
 The trisection construction is a ProductiveGenerator where:
 - pgen_seed = mkBisection 0 1 (initial [0,1] interval)
 - pgen_step = trisect_avoiding E n (choose third that avoids E(n)'s limit)
 - pgen_productive = trisect_shrinks (width decreases by factor 3)
*)

(** 
 L4 VERIFICATION FOR TRISECTION
 ==============================
 
 We must prove: trisect_step s deg s for all valid states.
 
 The SUFFICIENT REASON for the difference:
 
 1. PRECISION CRITERION CHANGE:
 - State at step n has precision 1/3^n
 - State at step n+1 has precision 1/3^(n+1) = (1/3) * 1/3^n
 - The precision IMPROVED by factor 3
 
 2. FORMAL STATEMENT:
 width(state_{n+1}) = width(state_n) / 3
 Since width(state_n) > 0, we have width(state_{n+1}) < width(state_n)
 Therefore state_{n+1} deg state_n
 
 3. THIS IS L4:
 The GROUND for distinction is the CHANGE IN PRECISION.
 It's not arbitrary - it's the refinement of the criterion.
 
 In Theory of Systems terms:
 - crit_predicate at step n: "approximation to precision 1/3^n"
 - crit_predicate at step n+1: "approximation to precision 1/3^(n+1)"
 - These are DIFFERENT criteria (P3: intensional identity)
 - Therefore the elements at n and n+1 are DISTINGUISHABLE (L4)
*)

(* ========================================================================= *)
(* SECTION 1: BASIC DEFINITIONS *)
(* ========================================================================= *)

(** A RealProcess is a sequence of rational approximations.
 This embodies P4: at any step n, we have a FINITE rational value.
 The "real number" emerges as the limit of the process. *)
Definition RealProcess := nat -> Q.

(** Cauchy property: approximations get arbitrarily close.
 This is the PROCESS formulation of convergence. *)
Definition is_Cauchy (R : RealProcess) : Prop :=
 forall eps, eps > 0 -> 
 exists N, forall m n, (m > N)%nat -> (n > N)%nat -> 
 Qabs (R m - R n) < eps.

(** REGULAR Cauchy property: convergence rate is KNOWN a priori.
 
 This is the key insight from Bishop's Constructive Analysis:
 A "good" process must have a predictable convergence rate.
 
 For index m > 0: |R(m) - R(n)| <= 1/m + 1/n
 
 This means: for precision eps, taking N = ceil(2/eps) suffices.
 The modulus of convergence is COMPUTABLE, not hidden in an existential.
 
 Philosophically (P4): A proper PROCESS must be controllable.
 We must know HOW FAST it converges, not just THAT it converges. *)
Definition is_Regular_Cauchy (R : RealProcess) : Prop :=
 forall m n : nat, (m > 0)%nat -> (n > 0)%nat ->
 Qabs (R m - R n) <= (1 # Pos.of_nat m) + (1 # Pos.of_nat n).

(** Computable modulus for regular Cauchy sequences.
 For precision 1/2^k, we need index > 2^(k+1). *)
Definition regular_modulus (k : nat) : nat := S (Nat.pow 2 (S k)).

(** An interval process: left and right endpoints at each step *)
Record IntervalProcess := mkIntervalProcess {
 ip_left : nat -> Q;
 ip_right : nat -> Q
}.

(** Midpoint process derived from interval process *)
Definition midpoint_process (I : IntervalProcess) : RealProcess :=
 fun n => (ip_left I n + ip_right I n) / 2.

(* ========================================================================= *)
(* SECTION 2: POWERS OF 2 *)
(* ========================================================================= *)

(** Helper: commutativity of addition respects Qle *)
Lemma Qplus_comm_le : forall a b : Q, a + b <= b + a.
Proof.
 intros a b.
 setoid_replace (a + b) with (b + a) by ring.
 apply Qle_refl.
Qed.

(** Helper: if a + b <= c, then a <= c - b *)
Lemma Qle_plus_to_minus : forall a b c : Q,
 a + b <= c -> a <= c - b.
Proof.
 intros a b c H.
 apply Qle_minus_iff.
 setoid_replace (c - b + - a) with (c + - (a + b)) by ring.
 apply Qle_minus_iff in H.
 exact H.
Qed.

Fixpoint pow2 (n : nat) : positive :=
 match n with 
 | O => 1%positive 
 | S n' => (2 * pow2 n')%positive 
 end.

Definition Qpow2 (n : nat) : Q := Z.pos (pow2 n) # 1.

Lemma Qpow2_pos : forall n, 0 < Qpow2 n.
Proof. intro. unfold Qpow2, Qlt. simpl. lia. Qed.

Lemma Qpow2_double : forall n, Qpow2 (S n) == 2 * Qpow2 n.
Proof.
 intro n. unfold Qpow2, Qeq, Qmult. simpl.
 rewrite Pos.mul_1_r. reflexivity.
Qed.

Lemma pow2_mono : forall m n, (m <= n)%nat -> (pow2 m <= pow2 n)%positive.
Proof. intros m n Hmn. induction Hmn; simpl; lia. Qed.

Lemma pow2_mono_Z : forall m n, (m <= n)%nat -> (Z.pos (pow2 m) <= Z.pos (pow2 n))%Z.
Proof. intros. apply Pos2Z.pos_le_pos. apply pow2_mono. exact H. Qed.

(* ========================================================================= *)
(* SECTION 2b: POWERS OF 3 (FOR TRISECTION) *)
(* ========================================================================= *)

Fixpoint pow3 (n : nat) : positive :=
 match n with 
 | O => 1%positive 
 | S n' => (3 * pow3 n')%positive 
 end.

Definition Qpow3 (n : nat) : Q := Z.pos (pow3 n) # 1.

Lemma Qpow3_pos : forall n, 0 < Qpow3 n.
Proof. intro. unfold Qpow3, Qlt. simpl. lia. Qed.

Lemma Qpow3_neq0 : forall n, ~ Qpow3 n == 0.
Proof. intro n. pose proof (Qpow3_pos n). unfold Qeq, Qlt in *. simpl in *. lia. Qed.

Lemma Qpow3_triple : forall n, Qpow3 (S n) == 3 * Qpow3 n.
Proof.
 intro n. unfold Qpow3, Qeq, Qmult. simpl.
 rewrite Pos.mul_1_r. reflexivity.
Qed.

Lemma pow3_pos : forall n, (0 < Z.pos (pow3 n))%Z.
Proof. intro. lia. Qed.

(** Key lemma: width after n trisection steps is 1/3^n *)
Lemma trisect_width_formula : forall n,
 1 / Qpow3 n > 0.
Proof.
 intro n.
 apply Qlt_shift_div_l.
 - apply Qpow3_pos.
 - ring_simplify. unfold Qlt; simpl; lia.
Qed.

(** The critical bound for trisection:
 If delta = 1/(12 * 3^n) and width = 1/3^n, then 2*delta < width/3.
 
 Proof: 2*delta = 2/(12*3^n) = 1/(6*3^n)
 width/3 = 1/(3*3^n) = 1/3^{n+1}
 We need: 1/(6*3^n) < 1/3^{n+1} = 1/(3*3^n)
 i.e., 3*3^n < 6*3^n, i.e., 3 < 6. TRUE!
*)
Lemma trisect_delta_bound : forall n,
 2 * (1 / (24 * Qpow3 n)) < (1 / Qpow3 n) / 3.
Proof.
 intro n.
 (* Key: 2/(24*3^n) = 1/(12*3^n) < 1/(3*3^n) = 1/(3^{n+1})
 Because 1/(12*3^n) < 1/(3*3^n) iff 3*3^n < 12*3^n iff 3 < 12 *)
 unfold Qdiv, Qlt, Qpow3, Qmult, Qinv. simpl. lia.
Qed.

(** 3^n grows without bound *)
Lemma pow3_ge_Sn : forall n, (Z.pos (pow3 n) >= Z.of_nat (S n))%Z.
Proof.
 induction n.
 - simpl. lia.
 - simpl pow3.
 replace (Z.pos (3 * pow3 n)) with (3 * Z.pos (pow3 n))%Z by lia.
 replace (Z.of_nat (S (S n))) with (Z.of_nat (S n) + 1)%Z by lia.
 lia.
Qed.

(* 3^k >= 3^N when k >= N *)
Lemma pow3_mono : forall k N, (N <= k)%nat -> (Z.pos (pow3 N) <= Z.pos (pow3 k))%Z.
Proof.
 intros k N H.
 induction H.
 - lia.
 - simpl. lia.
Qed.

(* 1/3^k <= 1/3^N when k >= N (inverse is anti-monotone) *)
Lemma Qpow3_inv_mono : forall k N, (N <= k)%nat -> 1 / Qpow3 k <= 1 / Qpow3 N.
Proof.
 intros k N H.
 unfold Qpow3, Qdiv, Qle, Qmult, Qinv. simpl.
 pose proof (pow3_mono k N H). lia.
Qed.

(** Archimedean property for powers of 3: for any eps > 0, exists N with 1/3^N < eps *)
Theorem Archimedean_pow3 : forall eps : Q, eps > 0 -> exists N : nat, 1 / Qpow3 N < eps.
Proof.
 intros eps Heps.
 (* eps = p/q where p,q > 0 *)
 (* Need 1/3^N < p/q, i.e., q < p * 3^N *)
 (* Since 3^N grows unboundedly, this is always achievable *)
 destruct eps as [p q].
 unfold Qlt in Heps. simpl in Heps.
 (* Heps: 0 * Z.pos q < p * 1, i.e., 0 < p *)
 assert (Hp : (0 < p)%Z) by lia.
 destruct p as [|p|p]; try lia.
 (* p = Z.pos p *)
 (* Need 1/3^N < (Z.pos p) / (Z.pos q), i.e., Z.pos q < Z.pos p * 3^N *)
 (* Equivalently: 3^N > q/p >= 1 *)
 (* Since 3^N >= N+1, take N = Pos.to_nat q *)
 exists (Pos.to_nat q).
 unfold Qlt, Qpow3, Qdiv, Qinv, Qmult. simpl.
 pose proof (pow3_ge_Sn (Pos.to_nat q)) as H.
 rewrite Nat2Z.inj_succ in H.
 rewrite positive_nat_Z in H.
 (* H: Z.pos (pow3 (Pos.to_nat q)) >= Z.pos q + 1 *)
 (* Goal: Z.pos q * 1 < Z.pos p * Z.pos (pow3 ...) *)
 (* i.e., Z.pos q < Z.pos p * Z.pos (pow3 ...) *)
 nia.
Qed.


(* ========================================================================= *)
(* SECTION 3: ARCHIMEDEAN PROPERTY *)
(* ========================================================================= *)

(** Key lemma: 2^n grows without bound.
 This is a THEOREM about natural numbers, not an axiom. *)
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

(** Archimedean property: for any ~ > 0, there exists N such that 1/2^N < ~ *)
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

(** Scaled Archimedean: for any width w > 0 and ~ > 0, there exists N such that w/2^N < ~ *)
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
 (* Goal: (wp * 1 * (1 * Z.pos eq) < ep * (Z.pos wq * Z.pos (pow2 N)))%Z *)
 (* Simplify: wp * eq < ep * wq * pow2(N) *)
 (* We know: pow2(N) > wp * eq, so wp * eq < pow2(N) *)
 (* And: ep * wq >= 1, so ep * wq * pow2(N) >= pow2(N) > wp * eq *)
 ring_simplify.
 (* Now: (wp * Z.pos eq < ep * Z.pos wq * Z.pos (pow2 N))%Z *)
 assert (H1 : (Z.pos (pow2 N) > wp * Z.pos eq)%Z) by exact HN.
 assert (H2 : (ep * Z.pos wq >= 1)%Z).
 { assert (Hep1 : (ep >= 1)%Z) by lia.
 assert (Hwq1 : (Z.pos wq >= 1)%Z) by lia.
 nia. }
 nia.
Qed.

(** Helper: 2^k > 0 *)
Lemma pow2_nat_pos : forall k, (Nat.pow 2 k > 0)%nat.
Proof.
 induction k; simpl; lia.
Qed.

(** Helper: 2^k <> 0 *)
Lemma pow2_nat_nonzero : forall k, (Nat.pow 2 k <> 0)%nat.
Proof.
 intro k. pose proof (pow2_nat_pos k). lia.
Qed.

(** Helper: pow2 k = Pos.of_nat (2^k) *)
Lemma pow2_eq_of_nat : forall k,
 pow2 k = Pos.of_nat (Nat.pow 2 k).
Proof.
 induction k; simpl.
 - reflexivity.
 - rewrite IHk.
 replace (Nat.pow 2 k + (Nat.pow 2 k + 0))%nat with (2 * Nat.pow 2 k)%nat by lia.
 rewrite Nat2Pos.inj_mul; [reflexivity | lia | apply pow2_nat_nonzero].
Qed.

(** Helper: If m > 2^k as nat, then 1/m < 1/2^k as Q *)
Lemma inv_mono_pow2 : forall m k,
 (m > Nat.pow 2 k)%nat ->
 (1 # Pos.of_nat m) < 1 / Qpow2 k.
Proof.
 intros m k Hm.
 unfold Qlt, Qdiv, Qpow2. simpl.
 apply Pos2Z.pos_lt_pos.
 rewrite pow2_eq_of_nat.
 rewrite <- Pos.compare_lt_iff.
 rewrite <- Nat2Pos.inj_compare.
 - rewrite Nat.compare_lt_iff. exact Hm.
 - apply pow2_nat_nonzero.
 - lia.
Qed.

(** Regular Cauchy implies standard Cauchy.
 This uses the Archimedean property to find suitable N. *)
Lemma Regular_implies_Cauchy : forall R,
 is_Regular_Cauchy R -> is_Cauchy R.
Proof.
 intros R Hreg.
 unfold is_Cauchy.
 intros eps Heps.
 (* For eps, we need 1/m + 1/n < eps *)
 (* Using Archimedean: exists N such that 1/2^N < eps/2 *)
 (* Then for m, n > 2^N: 1/m + 1/n <= 2/2^N < eps *)
 assert (Heps2 : eps / 2 > 0).
 { apply Qlt_shift_div_l; [unfold Qlt; simpl; lia | ring_simplify; exact Heps]. }
 destruct (Archimedean (eps/2) Heps2) as [k Hk].
 (* Take N = 2^k. For m, n > N: 1/m < 1/N = 1/2^k < eps/2 *)
 set (N := Nat.pow 2 k).
 exists N.
 intros m n Hm Hn.
 (* Apply regularity *)
 apply Qle_lt_trans with ((1 # Pos.of_nat m) + (1 # Pos.of_nat n)).
 - apply Hreg; lia.
 - (* 1/m + 1/n < eps when m, n > 2^k and 1/2^k < eps/2 *)
 (* For m > N = 2^k: 1/m < 1/2^k by inv_mono_pow2 *)
 (* And 1/2^k < eps/2 by Hk *)
 (* So 1/m < eps/2, similarly 1/n < eps/2 *)
 (* Thus 1/m + 1/n < eps *)
 
 assert (Hm_bound : (1 # Pos.of_nat m) < eps / 2).
 { apply Qlt_trans with (1 / Qpow2 k).
 - apply inv_mono_pow2. unfold N in Hm. exact Hm.
 - exact Hk. }
 
 assert (Hn_bound : (1 # Pos.of_nat n) < eps / 2).
 { apply Qlt_trans with (1 / Qpow2 k).
 - apply inv_mono_pow2. unfold N in Hn. exact Hn.
 - exact Hk. }
 
 (* 1/m + 1/n < eps/2 + eps/2 = eps *)
 apply Qlt_le_trans with (eps / 2 + eps / 2).
 + apply Qplus_lt_compat; assumption.
 + assert (Heq : eps / 2 + eps / 2 == eps) by field.
 rewrite Heq. apply Qle_refl.
Qed.

(* ========================================================================= *)
(* SECTION 4: WIDTH PROPERTIES *)
(* ========================================================================= *)

Lemma Qlt_minus_pos : forall a b : Q, a < b -> 0 < b - a.
Proof. intros. unfold Qlt, Qminus, Qplus, Qopp in *. simpl in *. lia. Qed.

Lemma width_shrinks : forall (w : Q) (m n : nat),
 w > 0 -> (m <= n)%nat -> w / Qpow2 n <= w / Qpow2 m.
Proof.
 intros w m n Hw Hmn.
 unfold Qle, Qdiv, Qmult, Qinv, Qpow2. destruct w as [wp wq]. simpl.
 pose proof (pow2_mono_Z m n Hmn).
 unfold Qlt in Hw. simpl in Hw.
 nia.
Qed.

(** Width after n halvings *)
Lemma halving_width : forall (a b : Q) (n : nat),
 a < b -> (b - a) / Qpow2 n > 0.
Proof.
 intros a b n Hab.
 apply Qlt_shift_div_l.
 - apply Qpow2_pos.
 - ring_simplify. apply Qlt_minus_pos. exact Hab.
Qed.

(* ========================================================================= *)
(* SECTION 5: FUNDAMENTAL THEOREM - SHRINKING ~ ~ ~ ~ ~ CAUCHY *)
(* ========================================================================= *)

(**
 THEOREM (Shrinking Intervals Form Cauchy Processes)
 
 This is the CENTRAL LEMMA that unifies IVT, EVT, and diagonal argument.
 
 PHILOSOPHICAL JUSTIFICATION (P4):
 - At each step n, we have a FINITE interval [left_n, right_n]
 - The width (right_n - left_n) is always FINITE
 - As n increases, width ~ ~ ~ ~ ~ 0 as a PROCESS
 - Any sequence of points within these intervals is Cauchy
 
 This embodies P4: infinity (the limit) is a property of the PROCESS,
 not an object we construct. We never "reach" the limit; we only
 generate increasingly precise approximations.
*)
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

(* ========================================================================= *)
(* SECTION 6: BISECTION-SPECIFIC LEMMAS *)
(* ========================================================================= *)

(** A bisection state: left and right bounds *)
Record BisectionState := mkBisection {
 bis_left : Q;
 bis_right : Q
}.

(** Initial width *)
Definition initial_width (s : BisectionState) : Q :=
 bis_right s - bis_left s.

(** Bisection step: choose left or right half based on some criterion *)
Definition bisect_left (s : BisectionState) : BisectionState :=
 mkBisection (bis_left s) ((bis_left s + bis_right s) / 2).

Definition bisect_right (s : BisectionState) : BisectionState :=
 mkBisection ((bis_left s + bis_right s) / 2) (bis_right s).

(** Width after bisection *)
Lemma bisect_left_width : forall s,
 bis_right (bisect_left s) - bis_left (bisect_left s) == 
 (bis_right s - bis_left s) / 2.
Proof.
 intro s. unfold bisect_left, bis_left, bis_right. simpl.
 destruct s as [l r]. simpl.
 (* Goal: (l + r) / 2 - l == (r - l) / 2 *)
 (* Equivalent to: (l + r - 2*l) / 2 == (r - l) / 2 *)
 (* Which is: (r - l) / 2 == (r - l) / 2 *)
 field.
Qed.

Lemma bisect_right_width : forall s,
 bis_right (bisect_right s) - bis_left (bisect_right s) == 
 (bis_right s - bis_left s) / 2.
Proof.
 intro s. unfold bisect_right, bis_left, bis_right. simpl.
 destruct s as [l r]. simpl.
 (* Goal: r - (l + r) / 2 == (r - l) / 2 *)
 (* Equivalent to: (2*r - l - r) / 2 == (r - l) / 2 *)
 (* Which is: (r - l) / 2 == (r - l) / 2 *)
 field.
Qed.

(** General bisection iteration - parameterized by choice function *)
Fixpoint bisect_iter (choose_half : BisectionState -> bool) (s : BisectionState) (n : nat) : BisectionState :=
 match n with
 | O => s
 | S n' => 
 let s' := bisect_iter choose_half s n' in
 if choose_half s' then bisect_left s' else bisect_right s'
 end.

(** KEY LEMMA: Width after n bisections *)
Lemma bisect_width_n : forall choose_half s n,
 bis_right (bisect_iter choose_half s n) - bis_left (bisect_iter choose_half s n) ==
 (bis_right s - bis_left s) / Qpow2 n.
Proof.
 intros choose_half s n. induction n.
 - (* Base case: n = 0, Qpow2 0 = 1 *)
 simpl. destruct s as [l r]. simpl.
 unfold Qpow2, Qdiv, Qeq, Qmult, Qinv, Qminus, Qplus, Qopp. simpl.
 destruct l as [lp lq]. destruct r as [rp rq]. simpl.
 lia.
 - simpl bisect_iter.
 destruct (choose_half (bisect_iter choose_half s n)) eqn:Hchoice.
 + (* Left half chosen *)
 rewrite bisect_left_width.
 rewrite IHn.
 rewrite Qpow2_double.
 destruct s as [l r]. simpl.
 (* Goal: (r - l) / Qpow2 n / 2 == (r - l) / (2 * Qpow2 n) *)
 field.
 (* Need to show Qpow2 n <> 0 *)
 intro H. pose proof (Qpow2_pos n). rewrite H in H0.
 apply Qlt_irrefl in H0. exact H0.
 + (* Right half chosen *)
 rewrite bisect_right_width.
 rewrite IHn.
 rewrite Qpow2_double.
 destruct s as [l r]. simpl.
 field.
 intro H. pose proof (Qpow2_pos n). rewrite H in H0.
 apply Qlt_irrefl in H0. exact H0.
Qed.

(** Nested intervals: each interval contains the next *)
(** Bisection preserves interval validity: if l <= r, then after bisection l' <= r' *)
Lemma bisect_left_valid : forall s,
 bis_left s <= bis_right s ->
 bis_left (bisect_left s) <= bis_right (bisect_left s).
Proof.
 intros [l r] Hlr. simpl in *.
 unfold Qle, Qdiv, Qplus, Qmult in *. simpl in *.
 destruct l as [lp lq]. destruct r as [rp rq]. simpl in *.
 (* Goal: lp * Z.pos rq * (Z.pos lq * 2) <= (lp * Z.pos rq + rp * Z.pos lq) * Z.pos lq * 1 *)
 (* Simplify: 2 * lp * rq * lq <= (lp * rq + rp * lq) * lq *)
 (* Since lp * rq <= rp * lq (from Hlr), we have 2 * lp * rq <= lp * rq + rp * lq *)
 nia.
Qed.

Lemma bisect_right_valid : forall s,
 bis_left s <= bis_right s ->
 bis_left (bisect_right s) <= bis_right (bisect_right s).
Proof.
 intros [l r] Hlr. simpl in *.
 unfold Qle, Qdiv, Qplus, Qmult in *. simpl in *.
 destruct l as [lp lq]. destruct r as [rp rq]. simpl in *.
 nia.
Qed.

Lemma bisect_iter_valid : forall choose_half s n,
 bis_left s <= bis_right s ->
 bis_left (bisect_iter choose_half s n) <= bis_right (bisect_iter choose_half s n).
Proof.
 intros choose_half s n Hs. induction n.
 - simpl. exact Hs.
 - simpl. destruct (choose_half (bisect_iter choose_half s n)).
 + apply bisect_left_valid. exact IHn.
 + apply bisect_right_valid. exact IHn.
Qed.

(** Helper: l <= (l + r) / 2 when l <= r *)
Lemma midpoint_ge_left : forall l r : Q,
 l <= r -> l <= (l + r) / 2.
Proof.
 intros [lp lq] [rp rq] Hlr. simpl in *.
 unfold Qle, Qdiv, Qplus, Qmult in *. simpl in *.
 nia.
Qed.

(** Helper: (l + r) / 2 <= r when l <= r *)
Lemma midpoint_le_right : forall l r : Q,
 l <= r -> (l + r) / 2 <= r.
Proof.
 intros [lp lq] [rp rq] Hlr. simpl in *.
 unfold Qle, Qdiv, Qplus, Qmult in *. simpl in *.
 nia.
Qed.

(** Nested intervals: each interval contains the next *)
Lemma bisect_nested_left : forall choose_half s n,
 bis_left s <= bis_right s ->
 bis_left s <= bis_left (bisect_iter choose_half s n).
Proof.
 intros choose_half s n Hs. induction n.
 - simpl. apply Qle_refl.
 - simpl. destruct (choose_half (bisect_iter choose_half s n)) eqn:Hc.
 + unfold bisect_left. simpl. exact IHn.
 + unfold bisect_right. simpl.
 apply Qle_trans with (bis_left (bisect_iter choose_half s n)).
 * exact IHn.
 * apply midpoint_ge_left. apply bisect_iter_valid. exact Hs.
Qed.

Lemma bisect_nested_right : forall choose_half s n,
 bis_left s <= bis_right s ->
 bis_right (bisect_iter choose_half s n) <= bis_right s.
Proof.
 intros choose_half s n Hs. induction n.
 - simpl. apply Qle_refl.
 - simpl. destruct (choose_half (bisect_iter choose_half s n)) eqn:Hc.
 + unfold bisect_left. simpl.
 apply Qle_trans with (bis_right (bisect_iter choose_half s n)).
 * apply midpoint_le_right. apply bisect_iter_valid. exact Hs.
 * exact IHn.
 + unfold bisect_right. simpl. exact IHn.
Qed.

(** Midpoint stays in original interval *)
Lemma bisect_midpoint_in_interval : forall choose_half s n,
 bis_left s <= bis_right s ->
 bis_left s <= (bis_left (bisect_iter choose_half s n) + bis_right (bisect_iter choose_half s n)) / 2 <= bis_right s.
Proof.
 intros choose_half s n Hs.
 split.
 - apply Qle_trans with (bis_left (bisect_iter choose_half s n)).
 + apply bisect_nested_left. exact Hs.
 + apply midpoint_ge_left. apply bisect_iter_valid. exact Hs.
 - apply Qle_trans with (bis_right (bisect_iter choose_half s n)).
 + apply midpoint_le_right. apply bisect_iter_valid. exact Hs.
 + apply bisect_nested_right. exact Hs.
Qed.

(** Interval at step n is contained in interval at step m when m <= n *)
Lemma bisect_iter_nested : forall choose_half s m n,
 bis_left s <= bis_right s ->
 (m <= n)%nat ->
 bis_left (bisect_iter choose_half s m) <= bis_left (bisect_iter choose_half s n) /\
 bis_right (bisect_iter choose_half s n) <= bis_right (bisect_iter choose_half s m).
Proof.
 intros choose_half s m n Hs Hmn.
 induction Hmn.
 - split; apply Qle_refl.
 - destruct IHHmn as [IHl IHr].
 simpl. destruct (choose_half (bisect_iter choose_half s m0)) eqn:Hc.
 + (* Left half *)
 split.
 * exact IHl.
 * apply Qle_trans with (bis_right (bisect_iter choose_half s m0)).
 -- apply midpoint_le_right. apply bisect_iter_valid. exact Hs.
 -- exact IHr.
 + (* Right half *)
 split.
 * apply Qle_trans with (bis_left (bisect_iter choose_half s m0)).
 -- exact IHl.
 -- apply midpoint_ge_left. apply bisect_iter_valid. exact Hs.
 * exact IHr.
Qed.

(** Key lemma: midpoint at step n lies within interval at step m when m <= n *)
Lemma midpoint_in_earlier_interval : forall choose_half s m n,
 bis_left s <= bis_right s ->
 (m <= n)%nat ->
 bis_left (bisect_iter choose_half s m) <= 
 (bis_left (bisect_iter choose_half s n) + bis_right (bisect_iter choose_half s n)) / 2 <=
 bis_right (bisect_iter choose_half s m).
Proof.
 intros choose_half s m n Hs Hmn.
 destruct (bisect_iter_nested choose_half s m n Hs Hmn) as [Hl Hr].
 split.
 - apply Qle_trans with (bis_left (bisect_iter choose_half s n)).
 + exact Hl.
 + apply midpoint_ge_left. apply bisect_iter_valid. exact Hs.
 - apply Qle_trans with (bis_right (bisect_iter choose_half s n)).
 + apply midpoint_le_right. apply bisect_iter_valid. exact Hs.
 + exact Hr.
Qed.

(** Difference of two points in an interval is bounded by width *)
Lemma points_in_interval_diff : forall l r x y : Q,
 l <= x <= r -> l <= y <= r -> Qabs (x - y) <= r - l.
Proof.
 intros l r x y [Hlx Hxr] [Hly Hyr].
 (* 
 Case x >= y: |x - y| = x - y <= r - l because x <= r and -y <= -l
 Case x < y: |x - y| = y - x <= r - l because y <= r and -x <= -l
 Both cases reduce to: max(x,y) - min(x,y) <= r - l
 which follows from l <= min(x,y) and max(x,y) <= r
 *)
 apply Qabs_case; intro Hxy.
 - (* x - y >= 0 *)
 apply Qle_trans with (x - l).
 + unfold Qle, Qminus, Qplus, Qopp in *. 
 destruct l as [lp lq], y as [yp yq]. simpl in *. nia.
 + unfold Qle, Qminus, Qplus, Qopp in *.
 destruct l as [lp lq], r as [rp rq], x as [xp xq]. simpl in *. nia.
 - (* x - y < 0, so |x - y| = -(x - y) = y - x *)
 apply Qle_trans with (y - l).
 + unfold Qle, Qlt, Qminus, Qplus, Qopp in *.
 destruct l as [lp lq], x as [xp xq]. simpl in *. nia.
 + unfold Qle, Qminus, Qplus, Qopp in *.
 destruct l as [lp lq], r as [rp rq], y as [yp yq]. simpl in *. nia.
Qed.

(** Midpoint process from bisection *)
Definition bisect_process (choose_half : BisectionState -> bool) (s : BisectionState) : RealProcess :=
 fun n => (bis_left (bisect_iter choose_half s n) + bis_right (bisect_iter choose_half s n)) / 2.

(** MAIN THEOREM: Bisection process is Cauchy *)
Theorem bisect_is_Cauchy : forall choose_half s,
 bis_left s < bis_right s ->
 is_Cauchy (bisect_process choose_half s).
Proof.
 intros choose_half s Hs.
 assert (Hs_le : bis_left s <= bis_right s) by (apply Qlt_le_weak; exact Hs).
 apply (shrinking_interval_Cauchy (bisect_process choose_half s) (bis_left s) (bis_right s)).
 - exact Hs.
 - intros m n Hmn.
 unfold bisect_process.
 (* Both midpoints lie within interval at step m *)
 assert (Hm_mid : bis_left (bisect_iter choose_half s m) <= 
 (bis_left (bisect_iter choose_half s m) + bis_right (bisect_iter choose_half s m)) / 2 <=
 bis_right (bisect_iter choose_half s m)).
 { split.
 - apply midpoint_ge_left. apply bisect_iter_valid. exact Hs_le.
 - apply midpoint_le_right. apply bisect_iter_valid. exact Hs_le. }
 assert (Hn_in_m : bis_left (bisect_iter choose_half s m) <=
 (bis_left (bisect_iter choose_half s n) + bis_right (bisect_iter choose_half s n)) / 2 <=
 bis_right (bisect_iter choose_half s m)).
 { apply midpoint_in_earlier_interval; assumption. }
 (* Apply points_in_interval_diff *)
 apply Qle_trans with (bis_right (bisect_iter choose_half s m) - bis_left (bisect_iter choose_half s m)).
 + apply points_in_interval_diff; assumption.
 + (* Width at step m equals (b - a) / 2^m *)
 rewrite bisect_width_n.
 apply Qle_refl.
Qed.

(* ========================================================================= *)
(* SECTION 7: GEOMETRIC SERIES FOR DIAGONAL *)
(* ========================================================================= *)

(** Powers of 10 for decimal representation *)
Fixpoint pow10 (n : nat) : positive :=
 match n with 
 | O => 1%positive 
 | S n' => (10 * pow10 n')%positive 
 end.

Definition Qpow10 (n : nat) : Q := Z.pos (pow10 n) # 1.

Lemma Qpow10_pos : forall n, 0 < Qpow10 n.
Proof. intro. unfold Qpow10, Qlt. simpl. lia. Qed.

(** Geometric series bound: sum of 8/10^k from k=1 to n is bounded by 8/9 *)
(** This is needed for the diagonal argument *)

(* First prove equality, then derive inequality *)
Lemma geometric_bound_eq : forall n : nat,
 8 / Qpow10 (S n) == (8#9) / Qpow10 n - (8#9) / Qpow10 (S n).
Proof.
 intro n.
 unfold Qpow10.
 setoid_replace (Z.pos (10 * pow10 n) # 1) with (10 * (Z.pos (pow10 n) # 1))
 by (unfold Qeq; simpl; ring).
 set (q := (Z.pos (pow10 n) # 1)).
 field.
 intro H. unfold q in H. unfold Qeq in H. simpl in H. lia.
Qed.

Lemma geometric_bound_step : forall n : nat,
 8 / Qpow10 (S n) <= (8#9) / Qpow10 n - (8#9) / Qpow10 (S n).
Proof.
 intro n.
 rewrite geometric_bound_eq.
 apply Qle_refl.
Qed.

(** Sum of 8/10^k for k=1..n equals 8/9 * (1 - 1/10^n) *)
Fixpoint digit_sum (n : nat) : Q :=
 match n with
 | O => 0
 | S n' => digit_sum n' + 8 / Qpow10 n
 end.

Lemma digit_sum_closed : forall n,
 digit_sum n == (8#9) - (8#9) / Qpow10 n.
Proof.
 induction n.
 - (* Base case: digit_sum 0 = 0 = (8/9) - (8/9)/1 *)
 simpl. unfold Qpow10, Qeq, Qdiv, Qminus, Qplus, Qopp, Qmult, Qinv. simpl. lia.
 - (* Inductive step: use recurrence relation *)
 simpl digit_sum. rewrite IHn.
 unfold Qpow10.
 (* Key: replace Z.pos (10 * p) with 10 * Z.pos p for field *)
 setoid_replace (Z.pos (10 * pow10 n) # 1) with (10 * (Z.pos (pow10 n) # 1))
 by (unfold Qeq; simpl; ring).
 set (q := (Z.pos (pow10 n) # 1)).
 field.
 (* Prove q ~ ~ deg ~ 0 *)
 unfold q. intro H. unfold Qeq in H. simpl in H. lia.
Qed.

Lemma Qpow10_nonzero : forall n, ~ Qpow10 n == 0.
Proof.
 intro n. unfold Qpow10, Qeq. simpl. lia.
Qed.

Lemma digit_sum_bounded : forall n,
 digit_sum n < 8#9.
Proof.
 intro n.
 rewrite digit_sum_closed.
 (* Goal: (8#9) - (8#9)/Qpow10 n < 8#9 *)
 assert (Hpos : (8#9) / Qpow10 n > 0).
 { unfold Qdiv. apply Qmult_lt_0_compat.
 - reflexivity.
 - apply Qinv_lt_0_compat. apply Qpow10_pos. }
 (* (8#9) - positive < 8#9 *)
 apply Qlt_minus_iff.
 (* Goal: 0 < (8#9) - ((8#9) - (8#9)/Qpow10 n) *)
 setoid_replace ((8#9) - ((8#9) - (8#9)/Qpow10 n)) with ((8#9)/Qpow10 n) by ring.
 exact Hpos.
Qed.

(** Archimedean for powers of 10 *)

(* Helper: pow10 grows faster than n *)
Lemma pow10_S_eq : forall n, pow10 (S n) = (10 * pow10 n)%positive.
Proof. intro n. reflexivity. Qed.

Lemma pow10_ge_n : forall n, (Z.pos (pow10 n) > Z.of_nat n)%Z.
Proof.
 induction n.
 - simpl. lia.
 - rewrite pow10_S_eq.
 rewrite Pos2Z.inj_mul.
 rewrite Nat2Z.inj_succ.
 (* IH: Z.pos (pow10 n) > Z.of_nat n *)
 (* Goal: 10 * Z.pos (pow10 n) > Z.of_nat n + 1 *)
 (* Since pow10 n >= 1, we have 10 * pow10 n >= 10 > n + 1 for small n *)
 (* For larger n, 10 * pow10 n >> n + 1 *)
 assert (H10 : (10 * Z.pos (pow10 n) >= 10)%Z).
 { assert (Hpos : (Z.pos (pow10 n) >= 1)%Z) by lia. lia. }
 (* pow10 n > n implies 10 * pow10 n > 10 * n >= n + 1 for n >= 1 *)
 (* For n = 0: 10 * 1 = 10 > 1 ~ ~ ~ ~ ~ *)
 destruct n.
 + simpl. lia.
 + (* n = S n': pow10 (S n') > S n', so 10 * pow10 (S n') > 10 * S n' >= S n' + 1 *)
 assert (Hprev : (Z.pos (pow10 (S n)) > Z.of_nat (S n))%Z) by exact IHn.
 lia.
Qed.

Lemma pow10_exceeds : forall z : Z, (z > 0)%Z -> exists n, (Z.pos (pow10 n) > z)%Z.
Proof.
 intros z Hz.
 exists (Z.to_nat z + 1)%nat.
 pose proof (pow10_ge_n (Z.to_nat z + 1)) as H.
 rewrite Nat2Z.inj_add in H.
 rewrite Z2Nat.id in H by lia.
 simpl in H. lia.
Qed.

Lemma archimedean_pow10 : forall eps : Q, eps > 0 -> 
 exists N : nat, 1 / Qpow10 N < eps.
Proof.
 intros eps Heps.
 destruct eps as [p q].
 unfold Qlt in Heps. simpl in Heps.
 assert (Hp : (p > 0)%Z) by lia.
 (* We need: 1 / 10^N < p/q, i.e., q < p * 10^N *)
 (* Find N such that 10^N > q *)
 destruct (pow10_exceeds (Z.pos q)) as [N HN].
 { lia. }
 exists N.
 unfold Qlt, Qdiv, Qmult, Qinv, Qpow10. simpl.
 (* Goal: 1 * Z.pos q * 1 < p * 1 * Z.pos (pow10 N) *)
 (* i.e., Z.pos q < p * Z.pos (pow10 N) *)
 (* Since p >= 1 and Z.pos (pow10 N) > Z.pos q, we have p * pow10 N >= pow10 N > q *)
 assert (Hp1 : (p >= 1)%Z) by lia.
 nia.
Qed.

(* ========================================================================= *)
(* SECTION 8: APPLICATIONS *)
(* ========================================================================= *)

(** 
 APPLICATION 1: IVT (Intermediate Value Theorem)
 
 Given f continuous with f(a) < 0 < f(b), bisection produces
 a Cauchy process converging to a root.
 
 The process:
 - At each step, test midpoint
 - Keep the half where sign change occurs
 - Width halves each step ~ ~ ~ ~ ~ Cauchy by our theorem
*)

(**
 APPLICATION 2: EVT (Extreme Value Theorem)
 
 Given f continuous on [a,b], max-search produces a Cauchy process
 converging to the maximum.
 
 The process:
 - At each step, compare f at 1/3 and 2/3 points
 - Keep the half with larger value
 - Width shrinks by factor ~ ~ deg ~ 1/2 each step ~ ~ ~ ~ ~ Cauchy
*)

(**
 APPLICATION 3: Diagonal Argument
 
 Given any enumeration of [0,1], the diagonal construction produces
 a real not in the enumeration.
 
 The process:
 - At step n, choose digit different from n-th digit of n-th real
 - The partial sums form a Cauchy sequence (geometric series)
 - The limit differs from every enumerated real
*)

(* ========================================================================= *)
(* SECTION 9: UNCOUNTABILITY VIA NESTED INTERVALS *)
(* ========================================================================= *)

(**
 IMPLEMENTATION OF APPLICATION 3: Diagonal Argument via Nested Intervals
 
 KEY INSIGHT:
 Instead of extracting digits (which is discontinuous), we use 
 "soft discretization": look at where E_n approximately is,
 then choose the OPPOSITE half.
 
 This avoids the boundary problem of extract_digit.
 
 PHILOSOPHY (Theory of Systems):
 - We don't "read" the structure of E_n (which is unknown)
 - We DISTINGUISH position and choose opposite
 - The act of distinction (L1-L5) is primary
*)

(** Enumeration: a sequence of real processes *)
Definition Enumeration := nat -> RealProcess.

(** Valid enumeration: each element is Cauchy and in [0,1] *)
Definition valid_enumeration (E : Enumeration) : Prop :=
 forall n, is_Cauchy (E n) /\ 
 (forall m, 0 <= E n m <= 1).

(** REGULAR valid enumeration: each element is REGULAR Cauchy and in [0,1].
 This is the stronger condition needed for the adaptive diagonal. *)
Definition valid_regular_enumeration (E : Enumeration) : Prop :=
 forall n, is_Regular_Cauchy (E n) /\ 
 (forall m, 0 <= E n m <= 1).

(** Regular enumeration implies standard enumeration *)
Lemma valid_regular_implies_valid : forall E,
 valid_regular_enumeration E -> valid_enumeration E.
Proof.
 intros E Hreg n.
 destruct (Hreg n) as [Hreg_cauchy Hbounds].
 split.
 - apply Regular_implies_Cauchy. exact Hreg_cauchy.
 - exact Hbounds.
Qed.

(** Two processes are equivalent if they converge to the same limit *)
Definition equiv (R1 R2 : RealProcess) : Prop :=
 forall eps, eps > 0 -> exists N, forall m,
 (m > N)%nat -> Qabs (R1 m - R2 m) < eps.

Definition not_equiv (R1 R2 : RealProcess) : Prop :=
 exists eps, eps > 0 /\ forall N, exists m,
 (m > N)%nat /\ Qabs (R1 m - R2 m) >= eps.

(** Indexed bisection: choose_half depends on step number *)
Fixpoint bisect_iter_indexed (choose_half : nat -> BisectionState -> bool) 
 (s : BisectionState) (n : nat) : BisectionState :=
 match n with
 | O => s
 | S n' => 
 let s' := bisect_iter_indexed choose_half s n' in
 if choose_half n' s' then bisect_left s' else bisect_right s'
 end.

(** Width lemma for indexed version *)
Lemma bisect_width_n_indexed : forall choose_half s n,
 bis_right (bisect_iter_indexed choose_half s n) - bis_left (bisect_iter_indexed choose_half s n) ==
 (bis_right s - bis_left s) / Qpow2 n.
Proof.
 intros choose_half s n. induction n.
 - simpl. destruct s as [l r]. simpl.
 unfold Qpow2, Qdiv, Qeq, Qmult, Qinv, Qminus, Qplus, Qopp. simpl.
 destruct l as [lp lq]. destruct r as [rp rq]. simpl. lia.
 - simpl bisect_iter_indexed.
 destruct (choose_half n (bisect_iter_indexed choose_half s n)) eqn:Hchoice.
 + rewrite bisect_left_width. rewrite IHn. rewrite Qpow2_double.
 destruct s as [l r]. simpl. field.
 intro H. pose proof (Qpow2_pos n). rewrite H in H0.
 apply Qlt_irrefl in H0. exact H0.
 + rewrite bisect_right_width. rewrite IHn. rewrite Qpow2_double.
 destruct s as [l r]. simpl. field.
 intro H. pose proof (Qpow2_pos n). rewrite H in H0.
 apply Qlt_irrefl in H0. exact H0.
Qed.

(** Validity preservation for indexed version *)
Lemma bisect_iter_indexed_valid : forall choose_half s n,
 bis_left s <= bis_right s ->
 bis_left (bisect_iter_indexed choose_half s n) <= bis_right (bisect_iter_indexed choose_half s n).
Proof.
 intros choose_half s n Hs. induction n.
 - simpl. exact Hs.
 - simpl. destruct (choose_half n (bisect_iter_indexed choose_half s n)).
 + apply bisect_left_valid. exact IHn.
 + apply bisect_right_valid. exact IHn.
Qed.

(** Nested property for indexed version *)
Lemma bisect_iter_indexed_nested : forall choose_half s m n,
 bis_left s <= bis_right s ->
 (m <= n)%nat ->
 bis_left (bisect_iter_indexed choose_half s m) <= bis_left (bisect_iter_indexed choose_half s n) /\
 bis_right (bisect_iter_indexed choose_half s n) <= bis_right (bisect_iter_indexed choose_half s m).
Proof.
 intros choose_half s m n Hs Hmn.
 induction Hmn.
 - split; apply Qle_refl.
 - destruct IHHmn as [IHl IHr].
 simpl. destruct (choose_half m0 (bisect_iter_indexed choose_half s m0)) eqn:Hchoice.
 + (* Left half chosen *)
 split.
 * exact IHl.
 * apply Qle_trans with (bis_right (bisect_iter_indexed choose_half s m0)).
 -- unfold bisect_left. simpl.
 apply midpoint_le_right. apply bisect_iter_indexed_valid. exact Hs.
 -- exact IHr.
 + (* Right half chosen *)
 split.
 * apply Qle_trans with (bis_left (bisect_iter_indexed choose_half s m0)).
 -- exact IHl.
 -- unfold bisect_right. simpl.
 apply midpoint_ge_left. apply bisect_iter_indexed_valid. exact Hs.
 * exact IHr.
Qed.

(** Midpoint process from indexed bisection *)
Definition bisect_process_indexed (choose_half : nat -> BisectionState -> bool) 
 (s : BisectionState) : RealProcess :=
 fun n => (bis_left (bisect_iter_indexed choose_half s n) + 
 bis_right (bisect_iter_indexed choose_half s n)) / 2.

(** Midpoint is in interval *)
Lemma midpoint_in_interval_indexed : forall choose_half s n,
 bis_left s <= bis_right s ->
 bis_left (bisect_iter_indexed choose_half s n) <= bisect_process_indexed choose_half s n <=
 bis_right (bisect_iter_indexed choose_half s n).
Proof.
 intros. unfold bisect_process_indexed. split.
 - apply midpoint_ge_left. apply bisect_iter_indexed_valid. exact H.
 - apply midpoint_le_right. apply bisect_iter_indexed_valid. exact H.
Qed.

(** Midpoint at step n lies within interval at step m when m <= n *)
Lemma midpoint_in_earlier_interval_indexed : forall choose_half s m n,
 bis_left s <= bis_right s ->
 (m <= n)%nat ->
 bis_left (bisect_iter_indexed choose_half s m) <= bisect_process_indexed choose_half s n <=
 bis_right (bisect_iter_indexed choose_half s m).
Proof.
 intros choose_half s m n Hs Hmn.
 destruct (bisect_iter_indexed_nested choose_half s m n Hs Hmn) as [Hl Hr].
 destruct (midpoint_in_interval_indexed choose_half s n Hs) as [Hml Hmr].
 split.
 - apply Qle_trans with (bis_left (bisect_iter_indexed choose_half s n)); assumption.
 - apply Qle_trans with (bis_right (bisect_iter_indexed choose_half s n)); assumption.
Qed.

(** Indexed bisection is Cauchy *)
Theorem bisect_indexed_is_Cauchy : forall choose_half s,
 bis_left s < bis_right s ->
 is_Cauchy (bisect_process_indexed choose_half s).
Proof.
 intros choose_half s Hs.
 assert (Hs_le : bis_left s <= bis_right s) by (apply Qlt_le_weak; exact Hs).
 apply (shrinking_interval_Cauchy (bisect_process_indexed choose_half s) (bis_left s) (bis_right s)).
 - exact Hs.
 - intros m n Hmn.
 assert (Hm_in : bis_left (bisect_iter_indexed choose_half s m) <= 
 bisect_process_indexed choose_half s m <=
 bis_right (bisect_iter_indexed choose_half s m)).
 { apply midpoint_in_interval_indexed. exact Hs_le. }
 assert (Hn_in_m : bis_left (bisect_iter_indexed choose_half s m) <=
 bisect_process_indexed choose_half s n <=
 bis_right (bisect_iter_indexed choose_half s m)).
 { apply midpoint_in_earlier_interval_indexed; assumption. }
 apply Qle_trans with (bis_right (bisect_iter_indexed choose_half s m) - 
 bis_left (bisect_iter_indexed choose_half s m)).
 + apply points_in_interval_diff; assumption.
 + rewrite bisect_width_n_indexed. apply Qle_refl.
Qed.

(* ========================================================================= *)
(* SECTION 10: AVOIDING ENUMERATION (BISECTION APPROACH) *)
(* *)
(* SUPERSEDED: This section uses BISECTION which has edge cases. *)
(* See SECTION 12b-12c for TRISECTION approach (FULLY PROVED). *)
(* Kept for reference and compatibility. *)
(* ========================================================================= *)

(** 
 KEY DEFINITION: Choose the half that EXCLUDES E_n
 
 Strategy:
 - Look at approximation E n (adaptive_ref n)
 - Compare to midpoint of current interval
 - If E_n is in left half, choose RIGHT (return false)
 - If E_n is in right half, choose LEFT (return true)
 
 This guarantees a gap between E_n and the chosen interval.
 
 CRITICAL CHANGE: For REGULAR Cauchy sequences, we use an ADAPTIVE ref
 that guarantees ref > M_E for the required precision.
 
 At step n:
 - Interval width = 1/2^n
 - Required precision: eps = 1/2^{n+3} (for gap analysis)
 - For regular sequence with |R(m) - R(k)| <= 1/m + 1/k:
 - We need 1/ref < eps/2 = 1/2^{n+4}
 - So ref > 2^{n+4} suffices
 - We take ref = 2^{n+5} to be safe
*)

(** Old fixed buffer - kept for compatibility *)
Definition precision_buffer : nat := 10.

(** Adaptive reference index for step n.
 For regular Cauchy sequences, this GUARANTEES ref > M_E. *)
Definition adaptive_ref (n : nat) : nat := Nat.pow 2 (n + 5).

(** The choice function that avoids E_n at step n - ADAPTIVE VERSION *)
Definition avoid_E_adaptive (E : Enumeration) : nat -> BisectionState -> bool :=
 fun n s =>
 let mid := (bis_left s + bis_right s) / 2 in
 let ref := adaptive_ref n in
 let approx := E n ref in
 if Qlt_le_dec approx mid then false else true.

(** The choice function that avoids E_n at step n - ORIGINAL VERSION *)
Definition avoid_E (E : Enumeration) : nat -> BisectionState -> bool :=
 fun n s =>
 let mid := (bis_left s + bis_right s) / 2 in
 let approx := E n (n + precision_buffer)%nat in
 (* If approx < mid, E_n is probably in left half, so choose RIGHT (false) *)
 (* If approx >= mid, E_n is probably in right half, so choose LEFT (true) *)
 if Qlt_le_dec approx mid then false else true.

(** The diagonal process via nested intervals - ADAPTIVE VERSION *)
Definition diagonal_intervals_adaptive (E : Enumeration) : RealProcess :=
 bisect_process_indexed (avoid_E_adaptive E) (mkBisection 0 1).

(** The diagonal process via nested intervals *)
Definition diagonal_intervals (E : Enumeration) : RealProcess :=
 bisect_process_indexed (avoid_E E) (mkBisection 0 1).

(** Initial interval is valid *)
Lemma unit_interval_valid : bis_left (mkBisection 0 1) < bis_right (mkBisection 0 1).
Proof. unfold Qlt. simpl. lia. Qed.

Lemma unit_interval_valid_le : bis_left (mkBisection 0 1) <= bis_right (mkBisection 0 1).
Proof. apply Qlt_le_weak. apply unit_interval_valid. Qed.

(** Diagonal is Cauchy *)
Theorem diagonal_intervals_is_Cauchy : forall E,
 is_Cauchy (diagonal_intervals E).
Proof.
 intro E. unfold diagonal_intervals.
 apply bisect_indexed_is_Cauchy.
 apply unit_interval_valid.
Qed.

(** Diagonal is in [0,1] *)
Theorem diagonal_intervals_in_unit : forall E m,
 0 <= diagonal_intervals E m <= 1.
Proof.
 intros E m. unfold diagonal_intervals.
 pose proof (midpoint_in_earlier_interval_indexed (avoid_E E) (mkBisection 0 1) 0 m 
 unit_interval_valid_le (Nat.le_0_l m)) as H.
 simpl in H. exact H.
Qed.

(* ========================================================================= *)
(* SECTION 10A: ADAPTIVE VERSION LEMMAS *)
(* ========================================================================= *)

(** Helper: if adaptive chose right (false), then E_n approximation was < mid *)
Lemma avoid_E_adaptive_chose_right : forall E n s,
 avoid_E_adaptive E n s = false ->
 E n (adaptive_ref n) < (bis_left s + bis_right s) / 2.
Proof.
 intros E n s H. unfold avoid_E_adaptive in H.
 destruct (Qlt_le_dec (E n (adaptive_ref n)) ((bis_left s + bis_right s) / 2)).
 - exact q.
 - discriminate H.
Qed.

(** Helper: if adaptive chose left (true), then E_n approximation was >= mid *)
Lemma avoid_E_adaptive_chose_left : forall E n s,
 avoid_E_adaptive E n s = true ->
 (bis_left s + bis_right s) / 2 <= E n (adaptive_ref n).
Proof.
 intros E n s H. unfold avoid_E_adaptive in H.
 destruct (Qlt_le_dec (E n (adaptive_ref n)) ((bis_left s + bis_right s) / 2)).
 - discriminate H.
 - exact q.
Qed.

(** The interval at step n - ADAPTIVE VERSION *)
Definition interval_at_adaptive (E : Enumeration) (n : nat) : BisectionState :=
 bisect_iter_indexed (avoid_E_adaptive E) (mkBisection 0 1) n.

(** Width at step n - ADAPTIVE VERSION *)
Lemma interval_width_at_adaptive : forall E n,
 bis_right (interval_at_adaptive E n) - bis_left (interval_at_adaptive E n) == 1 / Qpow2 n.
Proof.
 intros E n. unfold interval_at_adaptive.
 rewrite bisect_width_n_indexed. simpl.
 unfold Qdiv, Qminus, Qplus, Qopp. simpl. reflexivity.
Qed.

(** E_n's approximation is excluded from interval_{n+1} - ADAPTIVE VERSION *)
Lemma E_n_excluded_from_next_interval_adaptive : forall E n,
 let s_n := interval_at_adaptive E n in
 let s_n1 := interval_at_adaptive E (S n) in
 let approx := E n (adaptive_ref n) in
 (approx < bis_left s_n1) \/ (approx >= bis_right s_n1).
Proof.
 intros E n. simpl.
 unfold interval_at_adaptive. simpl.
 set (s_n := bisect_iter_indexed (avoid_E_adaptive E) (mkBisection 0 1) n).
 set (approx := E n (adaptive_ref n)).
 destruct (avoid_E_adaptive E n s_n) eqn:Hchoice.
 - (* Chose left (true): E_n approx >= mid, interval = [left, mid] *)
 right.
 pose proof (avoid_E_adaptive_chose_left E n s_n Hchoice) as Hmid.
 unfold bisect_left. simpl.
 exact Hmid.
 
 - (* Chose right (false): E_n approx < mid, interval = [mid, right] *)
 left.
 pose proof (avoid_E_adaptive_chose_right E n s_n Hchoice) as Hmid.
 unfold bisect_right. simpl.
 exact Hmid.
Qed.

(** Adaptive diagonal is in interval at any step *)
Lemma diagonal_adaptive_in_interval : forall E m,
 bis_left (interval_at_adaptive E m) <= diagonal_intervals_adaptive E m <= 
 bis_right (interval_at_adaptive E m).
Proof.
 intros E m. unfold diagonal_intervals_adaptive, interval_at_adaptive.
 apply midpoint_in_interval_indexed.
 apply unit_interval_valid_le.
Qed.

(** Adaptive diagonal at step m is in interval at step k when k <= m *)
Lemma diagonal_adaptive_in_earlier_interval : forall E k m,
 (k <= m)%nat ->
 bis_left (interval_at_adaptive E k) <= diagonal_intervals_adaptive E m <= 
 bis_right (interval_at_adaptive E k).
Proof.
 intros E k m Hkm. unfold diagonal_intervals_adaptive, interval_at_adaptive.
 apply midpoint_in_earlier_interval_indexed.
 - apply unit_interval_valid_le.
 - exact Hkm.
Qed.

(** KEY LEMMA: adaptive_ref is always large enough for regular sequences.
 For a regular Cauchy sequence, M_E for precision eps = 1/2^{n+3} is at most 2^{n+4}.
 Since adaptive_ref n = 2^{n+5} > 2^{n+4}, we always have ref > M_E. *)
Lemma adaptive_ref_exceeds_modulus : forall n,
 (adaptive_ref n > Nat.pow 2 (n + 4))%nat.
Proof.
 intro n. unfold adaptive_ref.
 (* 2^{n+5} > 2^{n+4} *)
 apply Nat.pow_lt_mono_r; lia.
Qed.

(** For regular sequences, 1/adaptive_ref < 1/2^{n+4} *)
Lemma adaptive_ref_precision : forall n,
 (1 # Pos.of_nat (adaptive_ref n)) < 1 / Qpow2 (n + 4).
Proof.
 intro n.
 unfold adaptive_ref.
 apply inv_mono_pow2.
 apply Nat.pow_lt_mono_r; lia.
Qed.

(** KEY LEMMA for regular sequences: E_n(m) is close to E_n(ref) for large m.
 
 For regular Cauchy R: |R(m) - R(k)| <= 1/m + 1/k
 
 When m, ref > 2^{n+4}:
 |E_n(m) - E_n(ref)| <= 1/m + 1/ref < 1/2^{n+4} + 1/2^{n+4} = 1/2^{n+3}
 
 Since adaptive_ref n = 2^{n+5} > 2^{n+4}, for any m > 2^{n+4}:
 |E_n(m) - E_n(adaptive_ref n)| < 1/2^{n+3} = interval_width / 4
 
 This is the critical bound that makes Case 1b/2b disappear! *)
Lemma regular_approx_close : forall E n m,
 valid_regular_enumeration E ->
 (m > Nat.pow 2 (n + 4))%nat ->
 Qabs (E n m - E n (adaptive_ref n)) < 1 / Qpow2 (n + 3).
Proof.
 intros E n m Hvalid Hm.
 destruct (Hvalid n) as [Hreg _].
 unfold is_Regular_Cauchy in Hreg.
 
 (* Apply regularity: |E_n(m) - E_n(ref)| <= 1/m + 1/ref *)
 assert (Hm_pos : (m > 0)%nat) by lia.
 assert (Href_pos : (adaptive_ref n > 0)%nat).
 { unfold adaptive_ref. 
 (* 2^{n+5} >= 2^0 = 1 > 0 *)
 assert (H : (Nat.pow 2 0 <= Nat.pow 2 (n + 5))%nat).
 { apply Nat.pow_le_mono_r. lia. lia. }
 simpl in H. lia. }
 
 specialize (Hreg m (adaptive_ref n) Hm_pos Href_pos).
 
 (* Now show: 1/m + 1/ref < 1/2^{n+3} *)
 apply Qle_lt_trans with ((1 # Pos.of_nat m) + (1 # Pos.of_nat (adaptive_ref n))).
 - exact Hreg.
 - (* 1/m + 1/ref < 1/2^{n+3} *)
 (* Since m > 2^{n+4}: 1/m < 1/2^{n+4} *)
 (* Since ref = 2^{n+5}: 1/ref < 1/2^{n+4} *)
 (* So 1/m + 1/ref < 2/2^{n+4} = 1/2^{n+3} *)
 
 assert (Hm_bound : (1 # Pos.of_nat m) < 1 / Qpow2 (n + 4)).
 { apply inv_mono_pow2. exact Hm. }
 
 assert (Href_bound : (1 # Pos.of_nat (adaptive_ref n)) < 1 / Qpow2 (n + 4)).
 { apply adaptive_ref_precision. }
 
 (* 1/m + 1/ref < 1/2^{n+4} + 1/2^{n+4} = 2/2^{n+4} = 1/2^{n+3} *)
 assert (Hsum : 1 / Qpow2 (n + 4) + 1 / Qpow2 (n + 4) == 1 / Qpow2 (n + 3)).
 { unfold Qdiv, Qpow2, Qplus, Qmult, Qinv, Qeq. simpl.
 replace (n + 4)%nat with (S (n + 3))%nat by lia.
 simpl pow2.
 nia. }
 
 apply Qlt_le_trans with (1 / Qpow2 (n + 4) + 1 / Qpow2 (n + 4)).
 + apply Qplus_lt_compat; assumption.
 + rewrite Hsum. apply Qle_refl.
Qed.

(** Consequence: For regular sequences, E_n(m) stays close to approx for all large m *)
Lemma regular_E_bounded_by_approx : forall E n m,
 valid_regular_enumeration E ->
 (m > adaptive_ref n)%nat ->
 let approx := E n (adaptive_ref n) in
 let eps := 1 / Qpow2 (n + 3) in
 approx - eps < E n m < approx + eps.
Proof.
 intros E n m Hvalid Hm approx eps.
 assert (Hclose : Qabs (E n m - approx) < eps).
 { apply regular_approx_close.
 - exact Hvalid.
 - unfold adaptive_ref in *.
 assert (Hadapt : (Nat.pow 2 (n + 5) > Nat.pow 2 (n + 4))%nat).
 { apply Nat.pow_lt_mono_r; lia. }
 lia.
 }
 apply Qabs_Qlt_condition in Hclose.
 destruct Hclose as [Hlow Hhigh].
 split.
 - (* approx - eps < E n m *)
 (* From Hlow: - eps < E n m - approx, i.e., approx - eps < E n m *)
 apply Qplus_lt_l with (- approx + eps).
 assert (Heq1 : approx - eps + (- approx + eps) == 0) by ring.
 assert (Heq2 : E n m + (- approx + eps) == E n m - approx + eps) by ring.
 rewrite Heq1, Heq2.
 apply Qplus_lt_l with (- eps).
 assert (Heq3 : 0 + - eps == - eps) by ring.
 assert (Heq4 : E n m - approx + eps + - eps == E n m - approx) by ring.
 rewrite Heq3, Heq4.
 (* Need: - eps < E n m - approx *)
 exact Hlow.
 - (* E n m < approx + eps *)
 (* From Hhigh: E n m - approx < eps, i.e., E n m < approx + eps *)
 apply Qplus_lt_l with (- approx).
 assert (Heq1 : E n m + - approx == E n m - approx) by ring.
 assert (Heq2 : approx + eps + - approx == eps) by ring.
 rewrite Heq1, Heq2.
 exact Hhigh.
Qed.

(* ========================================================================= *)
(* SECTION 11: KEY LEMMA - EXCLUSION *)
(* ========================================================================= *)

(**
 The crucial lemma: After step n+1, the interval EXCLUDES E_n.
 
 More precisely: E_n cannot be in the chosen half of the interval.
 The gap is at least half the interval width.
*)

(** Helper: if we chose right (false), then E_n approximation was < mid *)
Lemma avoid_E_chose_right : forall E n s,
 avoid_E E n s = false ->
 E n (n + precision_buffer)%nat < (bis_left s + bis_right s) / 2.
Proof.
 intros E n s H. unfold avoid_E in H.
 destruct (Qlt_le_dec (E n (n + precision_buffer)%nat) ((bis_left s + bis_right s) / 2)).
 - exact q.
 - discriminate H.
Qed.

(** Helper: if we chose left (true), then E_n approximation was >= mid *)
Lemma avoid_E_chose_left : forall E n s,
 avoid_E E n s = true ->
 (bis_left s + bis_right s) / 2 <= E n (n + precision_buffer)%nat.
Proof.
 intros E n s H. unfold avoid_E in H.
 destruct (Qlt_le_dec (E n (n + precision_buffer)%nat) ((bis_left s + bis_right s) / 2)).
 - discriminate H.
 - exact q.
Qed.

(** The interval at step n *)
Definition interval_at (E : Enumeration) (n : nat) : BisectionState :=
 bisect_iter_indexed (avoid_E E) (mkBisection 0 1) n.

(** Width at step n *)
Lemma interval_width_at : forall E n,
 bis_right (interval_at E n) - bis_left (interval_at E n) == 1 / Qpow2 n.
Proof.
 intros E n. unfold interval_at.
 rewrite bisect_width_n_indexed. simpl.
 unfold Qdiv, Qminus, Qplus, Qopp. simpl. reflexivity.
Qed.

(**
 KEY LEMMA: E_n's approximation is on the OPPOSITE side from where we went.
 
 At step n, we look at E_n and go to the opposite half.
 This means E_n (approx) is NOT STRICTLY INSIDE the interval at step n+1.
 
 Case avoid_E = true (go left): E_n >= mid, interval becomes [left, mid]
 => E_n >= mid = bis_right s_{n+1}, so E_n is at or beyond right boundary
 
 Case avoid_E = false (go right): E_n < mid, interval becomes [mid, right] 
 => E_n < mid = bis_left s_{n+1}, so E_n is strictly left of left boundary
 
 We use: E_n <= bis_left OR E_n >= bis_right (non-strict on one side)
*)
Lemma E_n_excluded_from_next_interval : forall E n,
 let s_n := interval_at E n in
 let s_n1 := interval_at E (S n) in
 let approx := E n (n + precision_buffer)%nat in
 (approx < bis_left s_n1) \/ (approx >= bis_right s_n1).
Proof.
 intros E n. simpl.
 unfold interval_at. simpl.
 set (s_n := bisect_iter_indexed (avoid_E E) (mkBisection 0 1) n).
 set (approx := E n (n + precision_buffer)%nat).
 destruct (avoid_E E n s_n) eqn:Hchoice.
 - (* Chose left (true): E_n approx >= mid, interval = [left, mid] *)
 right.
 pose proof (avoid_E_chose_left E n s_n Hchoice) as Hmid.
 unfold bisect_left. simpl.
 (* Goal: approx >= (bis_left s_n + bis_right s_n) / 2 *)
 (* Hmid says exactly this *)
 exact Hmid.
 
 - (* Chose right (false): E_n approx < mid, interval = [mid, right] *)
 left.
 pose proof (avoid_E_chose_right E n s_n Hchoice) as Hmid.
 unfold bisect_right. simpl.
 (* Goal: approx < (bis_left s_n + bis_right s_n) / 2 *)
 (* Hmid says exactly this *)
 exact Hmid.
Qed.

(** 
 The TRUE key lemma: After sufficient steps, E_n differs from diagonal
 by at least some epsilon.
 
 Strategy: 
 1. E_n's approximation at step n is excluded from interval at n+1
 2. The diagonal stays within all intervals
 3. By Cauchy property, E_n m converges to same limit as E_n (n+buffer)
 4. The gap is preserved
*)

Require Import Coq.Logic.Classical_Prop.

(** Helper: Diagonal is in interval at any step *)
Lemma diagonal_in_interval : forall E m,
 bis_left (interval_at E m) <= diagonal_intervals E m <= bis_right (interval_at E m).
Proof.
 intros E m. unfold diagonal_intervals, interval_at.
 apply midpoint_in_interval_indexed.
 apply unit_interval_valid_le.
Qed.

(** Helper: Diagonal at step m is in interval at step k when k <= m *)
Lemma diagonal_in_earlier_interval : forall E k m,
 (k <= m)%nat ->
 bis_left (interval_at E k) <= diagonal_intervals E m <= bis_right (interval_at E k).
Proof.
 intros E k m Hkm. unfold diagonal_intervals, interval_at.
 apply midpoint_in_earlier_interval_indexed.
 - apply unit_interval_valid_le.
 - exact Hkm.
Qed.

(** The gap between excluded point and interval boundary *)
Lemma exclusion_gap : forall E n,
 let s_n1 := interval_at E (S n) in
 let approx := E n (n + precision_buffer)%nat in
 (approx < bis_left s_n1) \/ (approx >= bis_right s_n1).
Proof.
 intros E n.
 apply E_n_excluded_from_next_interval.
Qed.

(** D(m) is strictly inside interval_k for k < m *)
(** D(m) = center of interval_m, and interval_m ~ interval_k *)
(** So D(m) is at distance >= width_m/2 from boundaries of interval_k *)
Lemma diagonal_strictly_inside : forall E k m,
 (k < m)%nat ->
 bis_left (interval_at E k) + 1 / Qpow2 m / 2 <= diagonal_intervals E m /\
 diagonal_intervals E m <= bis_right (interval_at E k) - 1 / Qpow2 m / 2.
Proof.
 intros E k m Hkm.
 unfold diagonal_intervals, interval_at.
 set (s_k := bisect_iter_indexed (avoid_E E) (mkBisection 0 1) k).
 set (s_m := bisect_iter_indexed (avoid_E E) (mkBisection 0 1) m).
 
 (* D(m) = center of s_m = (bis_left s_m + bis_right s_m) / 2 *)
 (* = bis_left s_m + width_m/2 = bis_right s_m - width_m/2 *)
 (* where width_m = 1/2^m *)
 
 (* s_m ~ s_k, so: *)
 (* bis_left s_k <= bis_left s_m <= bis_right s_m <= bis_right s_k *)
 
 (* D(m) = bis_left s_m + width_m/2 >= bis_left s_k + width_m/2 *)
 (* D(m) = bis_right s_m - width_m/2 <= bis_right s_k - width_m/2 *)
 
 pose proof (bisect_iter_indexed_nested (avoid_E E) (mkBisection 0 1) k m) as Hnest.
 assert (Hkm_le : (k <= m)%nat) by lia.
 specialize (Hnest unit_interval_valid_le Hkm_le).
 destruct Hnest as [Hleft Hright].
 
 pose proof (interval_width_at E m) as Hwidth_m.
 unfold interval_at in Hwidth_m.
 fold s_m in Hwidth_m.
 
 (* D(m) = (bis_left s_m + bis_right s_m) / 2 *)
 (* = bis_left s_m + (bis_right s_m - bis_left s_m) / 2 *)
 (* = bis_left s_m + width_m / 2 *)
 (* = bis_left s_m + (1/2^m) / 2 *)
 
 split.
 - (* bis_left s_k + 1/2^m/2 <= D(m) *)
 (* D(m) = bis_left s_m + width_m/2 *)
 (* bis_left s_m >= bis_left s_k (by Hleft) *)
 (* So D(m) >= bis_left s_k + width_m/2 *)
 
 assert (Hcenter : (bis_left s_m + bis_right s_m) / 2 == bis_left s_m + (bis_right s_m - bis_left s_m) / 2).
 { field. }
 apply Qle_trans with (bis_left s_m + (bis_right s_m - bis_left s_m) / 2).
 + (* bis_left s_k + 1/2^m/2 <= bis_left s_m + (bis_right s_m - bis_left s_m) / 2 *)
 rewrite Hwidth_m.
 apply Qplus_le_compat.
 * exact Hleft.
 * apply Qle_refl.
 + (* bis_left s_m + (bis_right s_m - bis_left s_m) / 2 <= D(m) *)
 rewrite <- Hcenter. apply Qle_refl.
 
 - (* D(m) <= bis_right s_k - 1/2^m/2 *)
 (* D(m) = bis_right s_m - width_m/2 *)
 (* bis_right s_m <= bis_right s_k (by Hright) *)
 (* So D(m) <= bis_right s_k - width_m/2 *)
 
 assert (Hcenter : (bis_left s_m + bis_right s_m) / 2 == bis_right s_m - (bis_right s_m - bis_left s_m) / 2).
 { field. }
 apply Qle_trans with (bis_right s_m - (bis_right s_m - bis_left s_m) / 2).
 + (* D(m) <= bis_right s_m - (bis_right s_m - bis_left s_m) / 2 *)
 rewrite <- Hcenter. apply Qle_refl.
 + (* bis_right s_m - (bis_right s_m - bis_left s_m) / 2 <= bis_right s_k - 1/2^m/2 *)
 rewrite Hwidth_m.
 apply Qplus_le_compat.
 * exact Hright.
 * apply Qopp_le_compat. apply Qle_refl.
Qed.

(** 
 STRONGER EXCLUSION: E_n's approximation is at distance >= width/2 from 
 the midpoint of interval n+1.
 
 This is because:
 - If we went left [L, M], then E_n >= M = right boundary of new interval
 - If we went right [M, R], then E_n < M = left boundary of new interval
 
 In either case, E_n is separated from the center of the new interval
 by at least width/4 of the parent interval.
*)

(** Helper for Q arithmetic: simplify midpoint calculations *)
Lemma bisect_left_midpoint : forall l r,
 (l + (l + r) / 2) / 2 == (3 * l + r) / 4.
Proof.
 intros l r. field.
Qed.

Lemma bisect_right_midpoint : forall l r,
 ((l + r) / 2 + r) / 2 == (l + 3 * r) / 4.
Proof.
 intros l r. field.
Qed.

Lemma midpoint_left_gap : forall l r,
 (l + r) / 2 - (l + (l + r) / 2) / 2 == (r - l) / 4.
Proof.
 intros l r. field.
Qed.

Lemma midpoint_right_gap : forall l r,
 ((l + r) / 2 + r) / 2 - (l + r) / 2 == (r - l) / 4.
Proof.
 intros l r. field.
Qed.

(* === GAP CALCULATION HELPERS === *)

(* Helper: 3*x representation in Z *)
Lemma Z_triple : forall x : Z,
 (match x with
 | 0 => 0
 | Z.pos y' => Z.pos (y' + y'~0)
 | Z.neg y' => Z.neg (y' + y'~0)
 end = 3 * x)%Z.
Proof. intro x. destruct x; simpl; lia. Qed.

Lemma pos_expand : forall p q r : positive,
 (Z.pos (p * q * r) = Z.pos p * Z.pos q * Z.pos r)%Z.
Proof. intros. lia. Qed.

Lemma Qabs_nonneg_eq : forall x, 0 <= x -> Qabs x == x.
Proof.
 intros x Hx. unfold Qabs. destruct x as [p q].
 unfold Qle in Hx. simpl in Hx.
 destruct p; simpl; try reflexivity. exfalso. lia.
Qed.

Lemma Qabs_nonpos_eq : forall x, x <= 0 -> Qabs x == -x.
Proof.
 intros x Hx. unfold Qabs. destruct x as [p q].
 unfold Qle in Hx. simpl in Hx.
 destruct p; simpl; try reflexivity. exfalso. lia.
Qed.

(** Key lemma: |x| <= y iff -y <= x /\ x <= y *)
Lemma Qabs_Qle_condition : forall x y, Qabs x <= y <-> -y <= x /\ x <= y.
Proof.
 intros x y.
 split.
 - (* |x| <= y -> -y <= x /\ x <= y *)
 intro H.
 split.
 + (* -y <= x *)
 apply Qle_trans with (- Qabs x).
 * apply Qopp_le_compat. exact H.
 * (* -|x| <= x *)
 destruct (Qlt_le_dec x 0) as [Hneg | Hpos].
 -- (* x < 0: |x| = -x, so -|x| = x *)
 rewrite (Qabs_nonpos_eq x).
 ++ ring_simplify. apply Qle_refl.
 ++ apply Qlt_le_weak. exact Hneg.
 -- (* x >= 0: |x| = x, so -|x| = -x <= x *)
 rewrite (Qabs_nonneg_eq x Hpos).
 apply Qle_trans with 0.
 ++ (* -x <= 0 *)
 unfold Qle, Qopp in *. simpl in *.
 destruct x as [xn xd]. simpl in *. lia.
 ++ exact Hpos.
 + (* x <= y *)
 apply Qle_trans with (Qabs x).
 * apply Qle_Qabs.
 * exact H.
 - (* -y <= x /\ x <= y -> |x| <= y *)
 intros [Hleft Hright].
 destruct (Qlt_le_dec x 0) as [Hneg | Hpos].
 + (* x < 0: |x| = -x *)
 rewrite (Qabs_nonpos_eq x).
 * (* -x <= y iff -y <= x *)
 apply Qopp_le_compat in Hleft.
 setoid_replace (- - y) with y in Hleft by ring.
 exact Hleft.
 * apply Qlt_le_weak. exact Hneg.
 + (* x >= 0: |x| = x *)
 rewrite (Qabs_nonneg_eq x Hpos).
 exact Hright.
Qed.

(* Midpoint ordering *)
Lemma left_mid_le_parent_mid : forall l r,
 l <= r -> (3 * l + r) / 4 <= (l + r) / 2.
Proof.
 intros l r Hlr.
 unfold Qle, Qplus, Qmult, Qdiv, Qinv in *.
 destruct l as [lp lq], r as [rp rq]. simpl in *.
 rewrite Z_triple. rewrite !pos_expand.
 replace (Z.pos lq ^ 2)%Z with (Z.pos lq * Z.pos lq)%Z by ring.
 replace (Z.pos rq ^ 2)%Z with (Z.pos rq * Z.pos rq)%Z by ring.
 assert (Hmain : (3 * lp * Z.pos rq + rp * Z.pos lq <= 
 2 * lp * Z.pos rq + 2 * rp * Z.pos lq)%Z) by nia.
 assert (Hscale : (0 < 2 * Z.pos lq * Z.pos rq)%Z) by nia.
 apply Z.mul_le_mono_pos_l with (p := (2 * Z.pos lq * Z.pos rq)%Z) in Hmain.
 2: exact Hscale. nia.
Qed.

Lemma parent_mid_le_right_mid : forall l r,
 l <= r -> (l + r) / 2 <= (l + 3 * r) / 4.
Proof.
 intros l r Hlr.
 unfold Qle, Qplus, Qmult, Qdiv, Qinv in *.
 destruct l as [lp lq], r as [rp rq]. simpl in *.
 rewrite Z_triple. rewrite !pos_expand.
 replace (Z.pos lq ^ 2)%Z with (Z.pos lq * Z.pos lq)%Z by ring.
 replace (Z.pos rq ^ 2)%Z with (Z.pos rq * Z.pos rq)%Z by ring.
 assert (Hmain : (2 * lp * Z.pos rq + 2 * rp * Z.pos lq <=
 lp * Z.pos rq + 3 * rp * Z.pos lq)%Z) by nia.
 assert (Hscale : (0 < 2 * Z.pos lq * Z.pos rq)%Z) by nia.
 apply Z.mul_le_mono_pos_l with (p := (2 * Z.pos lq * Z.pos rq)%Z) in Hmain.
 2: exact Hscale. nia.
Qed.

(* Gap identities *)
Lemma gap_left_identity : forall l r,
 (l + r) / 2 - (3 * l + r) / 4 == (r - l) / 4.
Proof. intros. field. Qed.

Lemma gap_right_identity : forall l r,
 (l + 3 * r) / 4 - (l + r) / 2 == (r - l) / 4.
Proof. intros. field. Qed.

Lemma neg_gap_right : forall l r,
 l <= r ->
 (l + r) / 2 - (l + 3 * r) / 4 <= 0.
Proof.
 intros l r Hlr.
 setoid_replace ((l + r) / 2 - (l + 3 * r) / 4) with
 (-((l + 3 * r) / 4 - (l + r) / 2)) by ring.
 setoid_replace ((l + 3 * r) / 4 - (l + r) / 2) with ((r - l) / 4) by field.
 unfold Qopp, Qle, Qminus, Qplus, Qdiv, Qmult, Qinv in *.
 destruct l as [lp lq], r as [rp rq]. simpl in *. lia.
Qed.

(* Gap case for left choice *)
Lemma gap_left_simplified : forall l r approx,
 l <= r ->
 (l + r) / 2 <= approx ->
 (l + r) / 2 - (3 * l + r) / 4 <= approx - (3 * l + r) / 4.
Proof.
 intros l r approx Hlr Happrox.
 apply Qplus_le_compat.
 - exact Happrox.
 - apply Qle_refl.
Qed.

Lemma gap_left_case : forall l r approx,
 l <= r ->
 (l + r) / 2 <= approx ->
 approx - (3 * l + r) / 4 >= (r - l) / 4.
Proof.
 intros l r approx Hlr Happrox.
 unfold Qge.
 pose proof (gap_left_simplified l r approx Hlr Happrox) as H.
 rewrite gap_left_identity in H.
 exact H.
Qed.

(* Gap case for right choice *)
Lemma gap_right_case : forall l r approx,
 l <= r ->
 approx < (l + r) / 2 ->
 (l + 3 * r) / 4 - approx >= (r - l) / 4.
Proof.
 intros l r approx Hlr Happrox.
 unfold Qge.
 assert (Hle : approx <= (l + r) / 2) by (unfold Qle, Qlt in *; lia).
 assert (H : (l + 3 * r) / 4 - (l + r) / 2 <= (l + 3 * r) / 4 - approx).
 { apply Qplus_le_compat. apply Qle_refl.
 unfold Qle, Qminus, Qplus, Qopp in *. destruct approx, ((l+r)/2). simpl in *. lia. }
 apply Qle_trans with ((l + 3 * r) / 4 - (l + r) / 2).
 - setoid_replace ((l + 3 * r) / 4 - (l + r) / 2) with ((r - l) / 4) by field.
 apply Qle_refl.
 - exact H.
Qed.

(* Qabs versions *)
Lemma gap_left_case_abs : forall l r approx,
 l <= r ->
 (l + r) / 2 <= approx ->
 Qabs (approx - (3 * l + r) / 4) >= (r - l) / 4.
Proof.
 intros l r approx Hlr Happrox.
 assert (Hdiff_nonneg : 0 <= approx - (3 * l + r) / 4).
 { apply Qle_trans with ((l + r) / 2 - (3 * l + r) / 4).
 - rewrite gap_left_identity.
 unfold Qle, Qminus, Qplus, Qopp, Qdiv, Qmult, Qinv in *.
 destruct l as [lp lq], r as [rp rq]. simpl in *. lia.
 - apply Qplus_le_compat; [exact Happrox | apply Qle_refl]. }
 rewrite Qabs_nonneg_eq by exact Hdiff_nonneg.
 apply gap_left_case; assumption.
Qed.

(* Helper for transitivity with Qeq *)
Lemma Qge_Qeq_compat : forall a b c, a == b -> b >= c -> a >= c.
Proof.
 intros a b c Hab Hbc. unfold Qge in *.
 apply Qle_trans with b.
 - exact Hbc.
 - rewrite Hab. apply Qle_refl.
Qed.

(* Helper for rewriting RHS of Qle *)
Lemma Qle_compat_r : forall x y z, x == y -> z <= y -> z <= x.
Proof. intros x y z Hxy Hzy. rewrite Hxy. exact Hzy. Qed.

(* Helper for rewriting LHS of Qle *)
Lemma Qle_compat_l : forall x y z, x == y -> x <= z -> y <= z.
Proof. intros x y z Hxy Hxz. rewrite <- Hxy. exact Hxz. Qed.

Lemma gap_right_case_abs : forall l r approx,
 l <= r ->
 approx < (l + r) / 2 ->
 Qabs (approx - (l + 3 * r) / 4) >= (r - l) / 4.
Proof.
 intros l r approx Hlr Happrox.
 assert (Hle : approx <= (l + r) / 2) by (unfold Qle, Qlt in *; lia).
 assert (Hdiff_neg : approx - (l + 3 * r) / 4 <= 0).
 { apply Qle_trans with ((l + r) / 2 - (l + 3 * r) / 4).
 - apply Qplus_le_compat; [exact Hle | apply Qle_refl].
 - apply neg_gap_right. exact Hlr. }
 assert (Heq : Qabs (approx - (l + 3 * r) / 4) == (l + 3 * r) / 4 - approx).
 { rewrite Qabs_nonpos_eq by exact Hdiff_neg. ring. }
 apply Qge_Qeq_compat with ((l + 3 * r) / 4 - approx).
 - exact Heq.
 - apply gap_right_case; assumption.
Qed.

(* === END GAP CALCULATION HELPERS === *)

Lemma exclusion_with_gap : forall E n,
 let s_n := interval_at E n in
 let s_n1 := interval_at E (S n) in
 let approx := E n (n + precision_buffer)%nat in
 let mid_n1 := (bis_left s_n1 + bis_right s_n1) / 2 in
 let width_n := bis_right s_n - bis_left s_n in
 (* E_n is at distance >= width_n/4 from the midpoint of interval n+1 *)
 Qabs (approx - mid_n1) >= width_n / 4.
Proof.
 intros E n.
 unfold interval_at. simpl.
 set (s_n := bisect_iter_indexed (avoid_E E) (mkBisection 0 1) n).
 set (approx := E n (n + precision_buffer)%nat).
 
 assert (Hvalid : bis_left s_n <= bis_right s_n).
 { unfold s_n. apply bisect_iter_indexed_valid. apply unit_interval_valid_le. }
 
 destruct (avoid_E E n s_n) eqn:Hchoice.
 - (* Chose left: new interval = bisect_left s_n *)
 pose proof (avoid_E_chose_left E n s_n Hchoice) as Hmid_le.
 unfold bisect_left. simpl.
 
 (* The midpoint identity *)
 assert (Hmid_eq : (bis_left s_n + (bis_left s_n + bis_right s_n) / 2) / 2 ==
 (3 * bis_left s_n + bis_right s_n) / 4).
 { apply bisect_left_midpoint. }
 
 (* Main result with simplified midpoint *)
 assert (Hgoal : Qabs (approx - (3 * bis_left s_n + bis_right s_n) / 4) >= 
 (bis_right s_n - bis_left s_n) / 4).
 { apply gap_left_case_abs; assumption. }
 
 (* Use Qabs_wd to show the two abs are equal *)
 unfold Qge in *.
 assert (Heq_abs : Qabs (approx - (bis_left s_n + (bis_left s_n + bis_right s_n) / 2) / 2) ==
 Qabs (approx - (3 * bis_left s_n + bis_right s_n) / 4)).
 { apply Qabs_wd. setoid_rewrite Hmid_eq. reflexivity. }
 
 (* Use Qle_compat_r: x == y -> z <= y -> z <= x *)
 apply Qle_compat_r with (Qabs (approx - (3 * bis_left s_n + bis_right s_n) / 4)).
 + exact Heq_abs.
 + exact Hgoal.
 
 - (* Chose right: new interval = bisect_right s_n *)
 pose proof (avoid_E_chose_right E n s_n Hchoice) as Hmid_gt.
 unfold bisect_right. simpl.
 
 assert (Hmid_eq : ((bis_left s_n + bis_right s_n) / 2 + bis_right s_n) / 2 ==
 (bis_left s_n + 3 * bis_right s_n) / 4).
 { apply bisect_right_midpoint. }
 
 assert (Hgoal : Qabs (approx - (bis_left s_n + 3 * bis_right s_n) / 4) >= 
 (bis_right s_n - bis_left s_n) / 4).
 { apply gap_right_case_abs; assumption. }
 
 unfold Qge in *.
 assert (Heq_abs : Qabs (approx - ((bis_left s_n + bis_right s_n) / 2 + bis_right s_n) / 2) ==
 Qabs (approx - (bis_left s_n + 3 * bis_right s_n) / 4)).
 { apply Qabs_wd. setoid_rewrite Hmid_eq. reflexivity. }
 
 apply Qle_compat_r with (Qabs (approx - (bis_left s_n + 3 * bis_right s_n) / 4)).
 + exact Heq_abs.
 + exact Hgoal.
Qed.


(* === QUANTITATIVE GAP BOUND === *)

(** D(n+2) is at least width_n/8 away from the boundary of interval_{n+1} *)
Lemma D_ref_distance_from_boundary : forall E n,
 let s_n1 := interval_at E (S n) in
 let ref := S (S n) in
 let D_ref := diagonal_intervals E ref in
 let width_n := bis_right (interval_at E n) - bis_left (interval_at E n) in
 bis_left s_n1 + width_n / 8 <= D_ref /\ D_ref <= bis_right s_n1 - width_n / 8.
Proof.
 intros E n.
 set (s_n := interval_at E n).
 set (s_n1 := interval_at E (S n)).
 set (s_n2 := interval_at E (S (S n))).
 set (ref := S (S n)).
 set (D_ref := diagonal_intervals E ref).
 set (width_n := bis_right s_n - bis_left s_n).
 
 (* D_ref = midpoint of interval_{n+2} *)
 assert (HD_mid : D_ref == (bis_left s_n2 + bis_right s_n2) / 2).
 { unfold D_ref, diagonal_intervals, s_n2, interval_at, ref.
 unfold bisect_process_indexed. reflexivity. }
 
 (* Width relationships - use interval_width_at directly *)
 assert (Hwidth_n_val : width_n == 1 / Qpow2 n).
 { unfold width_n, s_n. apply interval_width_at. }
 
 assert (Hwidth_n2_val : bis_right s_n2 - bis_left s_n2 == 1 / Qpow2 (S (S n))).
 { unfold s_n2. apply interval_width_at. }
 
 (* 1/2^{n+2} = (1/2^n) / 4 *)
 assert (Hwidth_ratio : 1 / Qpow2 (S (S n)) == (1 / Qpow2 n) / 4).
 { unfold Qpow2, Qdiv, Qmult, Qinv, Qeq. simpl pow2.
 destruct n; simpl; lia. }
 
 assert (Hwidth_n2 : bis_right s_n2 - bis_left s_n2 == width_n / 4).
 { setoid_rewrite Hwidth_n2_val. setoid_rewrite Hwidth_ratio.
 setoid_rewrite Hwidth_n_val. apply Qeq_refl. }
 
 (* interval_{n+2} ~ interval_{n+1} *)
 assert (Hnest : bis_left s_n1 <= bis_left s_n2 /\ bis_right s_n2 <= bis_right s_n1).
 { unfold s_n1, s_n2, interval_at.
 apply bisect_iter_indexed_nested.
 - apply unit_interval_valid_le.
 - lia. }
 destruct Hnest as [Hnest_l Hnest_r].
 
 (* D_ref = center of interval_{n+2}, so at distance width_{n+2}/2 from boundaries *)
 (* width_{n+2}/2 = width_n/8 *)
 
 assert (Hs_n2_valid : bis_left s_n2 <= bis_right s_n2).
 { unfold s_n2. apply bisect_iter_indexed_valid. apply unit_interval_valid_le. }
 
 (* Technical arithmetic - the key insight is that D_ref = midpoint of interval_{n+2},
 which is at distance width_{n+2}/2 = width_n/8 from the boundaries of interval_{n+2},
 and interval_{n+2} ~ interval_{n+1}, so D_ref is also at distance >= width_n/8
 from the boundaries of interval_{n+1} *)
 split.
 - (* bis_left s_n1 + width_n/8 <= D_ref *)
 apply Qle_trans with (bis_left s_n2 + width_n / 8).
 + apply Qplus_le_compat; [exact Hnest_l | apply Qle_refl].
 + (* D_ref = midpoint = bis_left s_n2 + width_{n+2}/2 = bis_left s_n2 + width_n/8 *)
 assert (Hcenter_left : (bis_left s_n2 + bis_right s_n2) / 2 == 
 bis_left s_n2 + (bis_right s_n2 - bis_left s_n2) / 2).
 { field. }
 
 assert (Hwidth_half : (bis_right s_n2 - bis_left s_n2) / 2 == width_n / 8).
 { rewrite Hwidth_n2. field. }
 
 (* D_ref == bis_left s_n2 + width_n/8 *)
 assert (HD_eq : D_ref == bis_left s_n2 + width_n / 8).
 { rewrite HD_mid. rewrite Hcenter_left. rewrite Hwidth_half. reflexivity. }
 
 (* Goal: bis_left s_n2 + width_n/8 <= D_ref *)
 (* Use Qle_lteq: x <= y <-> x < y \/ x == y *)
 apply Qle_lteq. right.
 symmetry. exact HD_eq.
 
 - (* D_ref <= bis_right s_n1 - width_n/8 *)
 apply Qle_trans with (bis_right s_n2 - width_n / 8).
 + (* D_ref = midpoint = bis_right s_n2 - width_{n+2}/2 = bis_right s_n2 - width_n/8 *)
 assert (Hcenter_right : (bis_left s_n2 + bis_right s_n2) / 2 == 
 bis_right s_n2 - (bis_right s_n2 - bis_left s_n2) / 2).
 { field. }
 
 assert (Hwidth_half : (bis_right s_n2 - bis_left s_n2) / 2 == width_n / 8).
 { rewrite Hwidth_n2. field. }
 
 (* D_ref == bis_right s_n2 - width_n/8 *)
 assert (HD_eq : D_ref == bis_right s_n2 - width_n / 8).
 { rewrite HD_mid. rewrite Hcenter_right. rewrite Hwidth_half. reflexivity. }
 
 (* Goal: D_ref <= bis_right s_n2 - width_n/8 *)
 apply Qle_lteq. right. exact HD_eq.
 
 + apply Qplus_le_compat; [exact Hnest_r | apply Qle_refl].
Qed.

(* ========================================================================= *)
(* ========================================================================= *)
(* SECTION 12B: TRISECTION - COMPLETE SOLUTION *)
(* ========================================================================= *)

(**
 TRISECTION CONSTRUCTION
 =======================
 
 The key insight: with bisection, the "confidence interval" around approx
 might straddle the midpoint, leaving the limit L_n possibly inside the
 chosen half.
 
 With TRISECTION:
 - Divide interval into 3 equal parts: [a, a+w/3], [a+w/3, a+2w/3], [a+2w/3, b]
 - Confidence interval has width 2/ref = 2/2^{n+5} = 1/2^{n+4}
 - Interval width is 1/2^n (using bisection width for previous steps)
 - One third has width 1/(3 * 2^n)
 - Since 1/2^{n+4} < 1/(3 * 2^n) for n >= 0 (check: 3 < 2^4 = 16 ~ )
 - The confidence interval fits in AT MOST 2 adjacent thirds
 - So we can ALWAYS choose a third that doesn't intersect the confidence interval
 - This GUARANTEES L_n is excluded from interval_{n+1}
*)

(** Trisection choice: which third to select *)
Inductive TrisectChoice : Set := TC_Left | TC_Middle | TC_Right.

(** Trisection step: select one of three thirds *)
Definition trisect_left (s : BisectionState) : BisectionState :=
 mkBisection (bis_left s) (bis_left s + (bis_right s - bis_left s) / 3).

Definition trisect_middle (s : BisectionState) : BisectionState :=
 mkBisection (bis_left s + (bis_right s - bis_left s) / 3)
 (bis_left s + 2 * (bis_right s - bis_left s) / 3).

Definition trisect_right (s : BisectionState) : BisectionState :=
 mkBisection (bis_left s + 2 * (bis_right s - bis_left s) / 3) (bis_right s).

Definition trisect_step (choice : TrisectChoice) (s : BisectionState) : BisectionState :=
 match choice with
 | TC_Left => trisect_left s
 | TC_Middle => trisect_middle s
 | TC_Right => trisect_right s
 end.

(** Width after trisection *)
Lemma trisect_left_width : forall s,
 bis_right (trisect_left s) - bis_left (trisect_left s) == 
 (bis_right s - bis_left s) / 3.
Proof.
 intros [l r]. simpl. field.
Qed.

Lemma trisect_middle_width : forall s,
 bis_right (trisect_middle s) - bis_left (trisect_middle s) == 
 (bis_right s - bis_left s) / 3.
Proof.
 intros [l r]. simpl. field.
Qed.

Lemma trisect_right_width : forall s,
 bis_right (trisect_right s) - bis_left (trisect_right s) == 
 (bis_right s - bis_left s) / 3.
Proof.
 intros [l r]. simpl. field.
Qed.

(** Helper: r >= l implies r - l >= 0 *)
Lemma Qminus_nonneg : forall l r : Q,
 l <= r -> 0 <= r - l.
Proof.
 intros l r Hlr.
 unfold Qle, Qminus, Qplus, Qopp in *.
 destruct l as [ln ld], r as [rn rd]. simpl in *.
 nia.
Qed.

(** Helper: x >= 0 implies x/3 >= 0 *)
Lemma Qdiv3_nonneg : forall x : Q,
 0 <= x -> 0 <= x / 3.
Proof.
 intros x Hx.
 unfold Qdiv.
 apply Qmult_le_0_compat.
 - exact Hx.
 - unfold Qle. simpl. lia.
Qed.

(** Helper: x/3 <= x for x >= 0 *)
Lemma Qdiv3_le : forall x : Q,
 0 <= x -> x / 3 <= x.
Proof.
 intros x Hx.
 unfold Qdiv, Qle, Qmult, Qinv in *. simpl in *.
 destruct x as [xn xd]. simpl in *. nia.
Qed.

(** Trisection preserves validity *)
Lemma trisect_left_valid : forall s,
 bis_left s <= bis_right s ->
 bis_left (trisect_left s) <= bis_right (trisect_left s).
Proof.
 intros [l r] Hlr. simpl in *.
 (* Goal: l <= l + (r - l) / 3 *)
 assert (H0 : 0 <= r - l) by (apply Qminus_nonneg; exact Hlr).
 assert (H1 : 0 <= (r - l) / 3) by (apply Qdiv3_nonneg; exact H0).
 apply Qle_trans with (l + 0).
 - rewrite Qplus_0_r. apply Qle_refl.
 - apply Qplus_le_compat.
 + apply Qle_refl.
 + exact H1.
Qed.

Lemma trisect_middle_valid : forall s,
 bis_left s <= bis_right s ->
 bis_left (trisect_middle s) <= bis_right (trisect_middle s).
Proof.
 intros [l r] Hlr. simpl in *.
 (* Goal: l + (r - l) / 3 <= l + 2 * (r - l) / 3 *)
 assert (H0 : 0 <= r - l) by (apply Qminus_nonneg; exact Hlr).
 assert (H1 : 0 <= (r - l) / 3) by (apply Qdiv3_nonneg; exact H0).
 apply Qplus_le_compat.
 - apply Qle_refl.
 - (* (r-l)/3 <= 2*(r-l)/3 *)
 unfold Qdiv.
 apply Qmult_le_compat_r.
 + apply Qle_trans with (1 * (r - l)).
 * ring_simplify. apply Qle_refl.
 * apply Qmult_le_compat_r; [unfold Qle; simpl; lia | exact H0].
 + unfold Qle. simpl. lia.
Qed.

Lemma trisect_right_valid : forall s,
 bis_left s <= bis_right s ->
 bis_left (trisect_right s) <= bis_right (trisect_right s).
Proof.
 intros [l r] Hlr. simpl in *.
 (* Goal: l + 2 * (r - l) / 3 <= r *)
 assert (H0 : 0 <= r - l) by (apply Qminus_nonneg; exact Hlr).
 assert (H1 : 0 <= (r - l) / 3) by (apply Qdiv3_nonneg; exact H0).
 assert (Heq : l + 2 * (r - l) / 3 == r - (r - l) / 3).
 { field. }
 rewrite Heq.
 apply Qplus_le_l with ((r - l) / 3).
 ring_simplify.
 apply Qle_trans with (r + 0).
 - rewrite Qplus_0_r. apply Qle_refl.
 - apply Qplus_le_compat. apply Qle_refl. exact H1.
Qed.

(** ===== NESTED INTERVAL LEMMAS ===== *)
(** These lemmas show that each trisection produces a subinterval *)

(* Helper: 0 <= 2*x when 0 <= x *)
Lemma Qmult_2_nonneg : forall x, 0 <= x -> 0 <= 2 * x.
Proof.
 intros x Hx.
 setoid_replace (2 * x) with (x + x) by ring.
 unfold Qle, Qplus in *. simpl in *. lia.
Qed.

Lemma trisect_left_right_bound : forall l r,
 l <= r -> l + (r - l) / 3 <= r.
Proof.
 intros l r Hlr.
 setoid_replace (l + (r - l) / 3) with ((2*l + r) / 3) by field.
 apply Qle_shift_div_r.
 - unfold Qlt. simpl. lia.
 - setoid_replace (r * 3) with (2 * r + r) by ring.
 apply Qplus_le_compat.
 + setoid_replace (2 * l) with (l * 2) by ring.
 setoid_replace (2 * r) with (r * 2) by ring.
 apply Qmult_le_compat_r; [exact Hlr | unfold Qle; simpl; lia].
 + apply Qle_refl.
Qed.

Lemma trisect_middle_left_bound : forall l r,
 l <= r -> l <= l + (r - l) / 3.
Proof.
 intros l r Hlr.
 assert (H0 : 0 <= r - l) by (apply Qminus_nonneg; exact Hlr).
 setoid_replace l with (l + 0) at 1 by ring.
 apply Qplus_le_compat. apply Qle_refl. apply Qdiv3_nonneg. exact H0.
Qed.

Lemma trisect_middle_right_bound : forall l r,
 l <= r -> l + 2 * (r - l) / 3 <= r.
Proof.
 intros l r Hlr.
 setoid_replace (l + 2 * (r - l) / 3) with ((l + 2*r) / 3) by field.
 apply Qle_shift_div_r.
 - unfold Qlt. simpl. lia.
 - setoid_replace (r * 3) with (r + 2 * r) by ring.
 apply Qplus_le_compat; [exact Hlr | apply Qle_refl].
Qed.

Lemma trisect_right_left_bound : forall l r,
 l <= r -> l <= l + 2 * (r - l) / 3.
Proof.
 intros l r Hlr.
 assert (H0 : 0 <= r - l) by (apply Qminus_nonneg; exact Hlr).
 setoid_replace l with (l + 0) at 1 by ring.
 apply Qplus_le_compat. apply Qle_refl.
 unfold Qdiv. apply Qmult_le_0_compat.
 + apply Qmult_2_nonneg. exact H0.
 + unfold Qle, Qinv. simpl. lia.
Qed.

(** Trisect_left produces a nested subinterval *)
Lemma trisect_left_nested : forall s,
 bis_left s <= bis_right s ->
 bis_left s <= bis_left (trisect_left s) /\
 bis_right (trisect_left s) <= bis_right s.
Proof.
 intros [l r] Hlr. simpl in *. split.
 - apply Qle_refl.
 - apply trisect_left_right_bound. exact Hlr.
Qed.

(** Trisect_middle produces a nested subinterval *)
Lemma trisect_middle_nested : forall s,
 bis_left s <= bis_right s ->
 bis_left s <= bis_left (trisect_middle s) /\
 bis_right (trisect_middle s) <= bis_right s.
Proof.
 intros [l r] Hlr. simpl in *. split.
 - apply trisect_middle_left_bound. exact Hlr.
 - apply trisect_middle_right_bound. exact Hlr.
Qed.

(** Trisect_right produces a nested subinterval *)
Lemma trisect_right_nested : forall s,
 bis_left s <= bis_right s ->
 bis_left s <= bis_left (trisect_right s) /\
 bis_right (trisect_right s) <= bis_right s.
Proof.
 intros [l r] Hlr. simpl in *. split.
 - apply trisect_right_left_bound. exact Hlr.
 - apply Qle_refl.
Qed.

(** Any trisect_step produces a nested subinterval *)
Lemma trisect_step_nested : forall choice s,
 bis_left s <= bis_right s ->
 bis_left s <= bis_left (trisect_step choice s) /\
 bis_right (trisect_step choice s) <= bis_right s.
Proof.
 intros choice s Hs.
 destruct choice.
 - apply trisect_left_nested. exact Hs.
 - apply trisect_middle_nested. exact Hs.
 - apply trisect_right_nested. exact Hs.
Qed.

(** ===== INTERVAL DIAMETER BOUND ===== *)

(* 0 <= b - a when a <= b *)
Lemma Qle_diff_nonneg : forall a b, a <= b -> 0 <= b - a.
Proof.
 intros a b H.
 apply Qle_minus_iff.
 setoid_replace (b - a + - 0) with (b - a) by ring.
 apply Qle_minus_iff in H.
 setoid_replace (b + - a) with (b - a) in H by ring.
 exact H.
Qed.

(* 0 <= x + y when 0 <= x and 0 <= y *)
Lemma Qplus_nonneg2 : forall x y, 0 <= x -> 0 <= y -> 0 <= x + y.
Proof.
 intros x y Hx Hy.
 apply Qle_trans with (0 + 0).
 - ring_simplify. apply Qle_refl.
 - apply Qplus_le_compat; assumption.
Qed.

(* If x, y both in [l, r], then |x - y| <= r - l *)
Lemma interval_diameter_bound : forall l r x y,
 l <= x <= r -> l <= y <= r -> Qabs (x - y) <= r - l.
Proof.
 intros l r x y [Hlx Hxr] [Hly Hyr].
 apply Qabs_Qle_condition.
 split.
 - (* -(r - l) <= x - y *)
 apply Qle_minus_iff.
 setoid_replace (x - y + - (-(r - l))) with ((x - l) + (r - y)) by ring.
 apply Qplus_nonneg2.
 + apply Qle_diff_nonneg. exact Hlx.
 + apply Qle_diff_nonneg. exact Hyr.
 - (* x - y <= r - l *)
 apply Qle_minus_iff.
 setoid_replace (r - l + - (x - y)) with ((r - x) + (y - l)) by ring.
 apply Qplus_nonneg2.
 + apply Qle_diff_nonneg. exact Hxr.
 + apply Qle_diff_nonneg. exact Hly.
Qed.

(** Lower bound on |x - y| when x and y are in separated intervals *)
(* |x - y| >= b - a when x >= b > a >= y *)
Lemma Qabs_gap_lower : forall x y a b,
 b <= x -> y <= a -> a < b -> Qabs (x - y) >= b - a.
Proof.
 intros x y a b Hbx Hya Hab.
 rewrite Qabs_pos.
 - (* x - y >= b - a *)
 apply Qle_minus_iff.
 setoid_replace (x - y + - (b - a)) with ((x - b) + (a - y)) by ring.
 apply Qle_trans with (0 + 0).
 + ring_simplify. apply Qle_refl.
 + apply Qplus_le_compat.
 * apply Qle_minus_iff. setoid_replace (x - b + - 0) with (x - b) by ring.
 apply Qle_minus_iff in Hbx. setoid_replace (x + - b) with (x - b) in Hbx by ring.
 exact Hbx.
 * apply Qle_minus_iff. setoid_replace (a - y + - 0) with (a - y) by ring.
 apply Qle_minus_iff in Hya. setoid_replace (a + - y) with (a - y) in Hya by ring.
 exact Hya.
 - (* 0 <= x - y *)
 apply Qle_minus_iff.
 setoid_replace (x - y + - 0) with (x - y) by ring.
 assert (Hxy : y < x).
 { apply Qle_lt_trans with a.
 - exact Hya.
 - apply Qlt_le_trans with b; assumption. }
 apply Qlt_le_weak.
 apply Qlt_minus_iff in Hxy.
 setoid_replace (x + - y) with (x - y) in Hxy by ring.
 exact Hxy.
Qed.

(* Symmetric case: |x - y| >= b - a when y >= b > a >= x *)
Lemma Qabs_gap_lower_sym : forall x y a b,
 b <= y -> x <= a -> a < b -> Qabs (x - y) >= b - a.
Proof.
 intros x y a b Hby Hxa Hab.
 rewrite Qabs_neg.
 - (* -(x - y) = y - x >= b - a *)
 setoid_replace (-(x - y)) with (y - x) by ring.
 apply Qle_minus_iff.
 setoid_replace (y - x + - (b - a)) with ((y - b) + (a - x)) by ring.
 apply Qle_trans with (0 + 0).
 + ring_simplify. apply Qle_refl.
 + apply Qplus_le_compat.
 * apply Qle_minus_iff. setoid_replace (y - b + - 0) with (y - b) by ring.
 apply Qle_minus_iff in Hby. setoid_replace (y + - b) with (y - b) in Hby by ring.
 exact Hby.
 * apply Qle_minus_iff. setoid_replace (a - x + - 0) with (a - x) by ring.
 apply Qle_minus_iff in Hxa. setoid_replace (a + - x) with (a - x) in Hxa by ring.
 exact Hxa.
 - (* x - y <= 0 *)
 apply Qle_minus_iff.
 ring_simplify.
 assert (Hxy : x < y).
 { apply Qle_lt_trans with a.
 - exact Hxa.
 - apply Qlt_le_trans with b; assumption. }
 apply Qlt_le_weak.
 apply Qlt_minus_iff in Hxy.
 (* Hxy: 0 < y + - x, goal: 0 < -1 * x + y *)
 setoid_replace (-1 * x + y) with (y + - x) by ring.
 exact Hxy.
Qed.

(** If |x - a| < d, then x < a + d *)
Lemma in_interval_upper : forall x a d,
 Qabs (x - a) < d -> x < a + d.
Proof.
 intros x a d H.
 apply Qabs_Qlt_condition in H.
 destruct H as [Hlow Hhigh].
 apply Qlt_minus_iff.
 setoid_replace (a + d + - x) with (d - (x - a)) by ring.
 apply Qlt_minus_iff in Hhigh.
 setoid_replace (d + - (x - a)) with (d - (x - a)) in Hhigh by ring.
 exact Hhigh.
Qed.

(** If |x - a| < d, then a - d < x *)
Lemma in_interval_lower : forall x a d,
 Qabs (x - a) < d -> a - d < x.
Proof.
 intros x a d H.
 apply Qabs_Qlt_condition in H.
 destruct H as [Hlow _].
 apply Qlt_minus_iff.
 setoid_replace (x + - (a - d)) with (x - a + d) by ring.
 apply Qlt_minus_iff in Hlow.
 setoid_replace (x - a + - - d) with (x - a + d) in Hlow by ring.
 exact Hlow.
Qed.

(** Confidence interval: [approx - delta, approx + delta] *)
Definition confidence_interval (approx delta : Q) : Q * Q :=
 (approx - delta, approx + delta).

(** Check if confidence interval is entirely below a point *)
Definition conf_below (approx delta boundary : Q) : bool :=
 if Qlt_le_dec (approx + delta) boundary then true else false.

(** Check if confidence interval is entirely above a point *)
Definition conf_above (approx delta boundary : Q) : bool :=
 if Qlt_le_dec boundary (approx - delta) then true else false.

(** Smart choice: select the third that doesn't intersect confidence interval *)
Definition smart_trisect_choice (s : BisectionState) (approx delta : Q) : TrisectChoice :=
 let w := bis_right s - bis_left s in
 let boundary1 := bis_left s + w / 3 in
 let boundary2 := bis_left s + 2 * w / 3 in
 (* If confidence interval is entirely in left third, choose right *)
 if conf_below approx delta boundary1 then TC_Right
 (* If confidence interval is entirely in right third, choose left *)
 else if conf_above approx delta boundary2 then TC_Left
 (* Otherwise confidence interval straddles middle, choose based on position *)
 else if conf_below approx delta boundary2 then TC_Right
 else TC_Left.

(** Helper: subtraction preserves inequality *)
Lemma Qle_minus_compat : forall a b c : Q,
 a <= b -> a - c <= b - c.
Proof.
 intros a b c H.
 unfold Qle, Qminus, Qplus, Qopp in *.
 destruct a as [an ad], b as [bn bd], c as [cn cd]. simpl in *.
 nia.
Qed.

(** Helper: x < y iff 0 < y - x *)
Lemma Qlt_sub_iff : forall x y : Q, x < y <-> 0 < y - x.
Proof.
 intros x y.
 unfold Qlt, Qminus, Qplus, Qopp.
 destruct x as [xn xd], y as [yn yd]. simpl.
 split; intro H; nia.
Qed.

(** If x < y, then z - y < z - x *)
Lemma Qminus_lt_compat_r : forall x y z,
 x < y -> z - y < z - x.
Proof.
 intros x y z H.
 apply Qlt_minus_iff.
 setoid_replace (z - x + - (z - y)) with (y - x) by ring.
 apply Qlt_minus_iff in H.
 setoid_replace (y + - x) with (y - x) in H by ring.
 exact H.
Qed.

(* If a < b - c then a + c < b *)
Lemma Qlt_minus_to_plus : forall a b c,
 a < b - c -> a + c < b.
Proof.
 intros a b c H.
 apply Qlt_minus_iff.
 setoid_replace (b + - (a + c)) with (b - c - a) by ring.
 apply Qlt_minus_iff in H.
 setoid_replace (b - c + - a) with (b - c - a) in H by ring.
 exact H.
Qed.

(** If conf_below approx delta b1 is true, then choice = TC_Right *)
Lemma conf_below_gives_right : forall s approx delta,
 let w := bis_right s - bis_left s in
 let b1 := bis_left s + w / 3 in
 approx + delta < b1 ->
 smart_trisect_choice s approx delta = TC_Right.
Proof.
 intros s approx delta w b1 Hlt.
 unfold smart_trisect_choice. fold w. fold b1.
 unfold conf_below.
 destruct (Qlt_le_dec (approx + delta) b1).
 - reflexivity.
 - exfalso. apply (Qlt_irrefl (approx + delta)).
 apply Qlt_le_trans with b1; assumption.
Qed.

(** If conf_above approx delta b2 is true, then choice = TC_Left *)
Lemma conf_above_gives_left : forall s approx delta,
 let w := bis_right s - bis_left s in
 let b1 := bis_left s + w / 3 in
 let b2 := bis_left s + 2 * w / 3 in
 ~ (approx + delta < b1) ->
 b2 < approx - delta ->
 smart_trisect_choice s approx delta = TC_Left.
Proof.
 intros s approx delta w b1 b2 Hnot_below Habove.
 unfold smart_trisect_choice. fold w. fold b1. fold b2.
 unfold conf_below, conf_above.
 destruct (Qlt_le_dec (approx + delta) b1).
 - exfalso. apply Hnot_below. exact q.
 - destruct (Qlt_le_dec b2 (approx - delta)).
 + reflexivity.
 + exfalso. apply (Qlt_irrefl b2).
 apply Qlt_le_trans with (approx - delta); assumption.
Qed.

(** Gap when TC_Right is chosen: gap > w/3 *)
Lemma gap_when_right : forall s approx delta,
 bis_left s < bis_right s ->
 let w := bis_right s - bis_left s in
 let b1 := bis_left s + w / 3 in
 let b2 := bis_left s + 2 * w / 3 in
 approx + delta < b1 ->
 b2 - (approx + delta) > w / 3.
Proof.
 intros s approx delta Hvalid w b1 b2 Hlt.
 (* b2 - (approx + delta) > b2 - b1 = w/3 *)
 assert (Hgap : b2 - b1 == w / 3).
 { unfold b2, b1, w. field. }
 assert (Hstep : b2 - b1 < b2 - (approx + delta)).
 { apply Qminus_lt_compat_r. exact Hlt. }
 rewrite Hgap in Hstep. exact Hstep.
Qed.

(** Gap when TC_Left is chosen: gap > w/3 *)
Lemma gap_when_left : forall s approx delta,
 bis_left s < bis_right s ->
 let w := bis_right s - bis_left s in
 let b1 := bis_left s + w / 3 in
 let b2 := bis_left s + 2 * w / 3 in
 b2 < approx - delta ->
 (approx - delta) - b1 > w / 3.
Proof.
 intros s approx delta Hvalid w b1 b2 Hlt.
 (* (approx - delta) - b1 > b2 - b1 = w/3 *)
 assert (Hgap : b2 - b1 == w / 3).
 { unfold b2, b1, w. field. }
 assert (Hstep : b2 - b1 < (approx - delta) - b1).
 { apply Qlt_minus_iff.
 setoid_replace ((approx - delta) - b1 + - (b2 - b1)) with ((approx - delta) - b2) by ring.
 apply Qlt_minus_iff in Hlt.
 setoid_replace (approx - delta + - b2) with ((approx - delta) - b2) in Hlt by ring.
 exact Hlt. }
 rewrite Hgap in Hstep. exact Hstep.
Qed.

(** w/3 > 6*delta for our synchronized parameters - see third_width_gt_6_delta below *)

(** The smart choice guarantees the confidence interval is excluded *)
Lemma smart_choice_excludes_confidence : forall s approx delta,
 bis_left s <= bis_right s ->
 delta > 0 ->
 2 * delta < (bis_right s - bis_left s) / 3 ->
 let choice := smart_trisect_choice s approx delta in
 let s' := trisect_step choice s in
 (* Either approx + delta < bis_left s' OR approx - delta > bis_right s' *)
 (approx + delta < bis_left s') \/ (bis_right s' < approx - delta).
Proof.
 intros s approx delta Hs Hdelta_pos Hdelta_small.
 set (w := bis_right s - bis_left s).
 set (b1 := bis_left s + w / 3).
 set (b2 := bis_left s + 2 * w / 3).
 
 (* First establish w > 0 from 2*delta < w/3 and delta > 0 *)
 assert (Hw_pos : 0 < w).
 { (* w/3 > 2*delta > 0, so w/3 > 0, so w > 0 *)
 assert (H : 0 < w / 3).
 { apply Qlt_trans with (2 * delta).
 - apply Qmult_lt_0_compat; [unfold Qlt; simpl; lia | exact Hdelta_pos].
 - exact Hdelta_small.
 }
 unfold Qdiv in H.
 apply Qmult_lt_r with (/ 3).
 - unfold Qlt; simpl; lia.
 - setoid_rewrite Qmult_0_l. exact H.
 }
 
 (* b1 < b2 follows from w > 0 *)
 assert (Hb1_lt_b2 : b1 < b2).
 { unfold b1, b2.
 apply Qplus_lt_r.
 (* Need: w/3 < 2*w/3 *)
 unfold Qdiv.
 apply Qmult_lt_compat_r.
 - unfold Qlt; simpl; lia.
 - (* w < 2*w when w > 0 *)
 apply Qlt_minus_iff.
 setoid_replace (2 * w - w) with w by ring.
 exact Hw_pos.
 }
 
 (* Unfold the smart choice *)
 unfold smart_trisect_choice, conf_below, conf_above.
 fold w b1 b2.
 
 (* Case analysis *)
 destruct (Qlt_le_dec (approx + delta) b1) as [Hcase1 | Hcase1'].
 
 - (* Case 1: approx + delta < b1 -> choose right *)
 simpl. left.
 apply Qlt_trans with b1; [exact Hcase1 | exact Hb1_lt_b2].
 
 - destruct (Qlt_le_dec b2 (approx - delta)) as [Hcase2 | Hcase2'].
 
 + (* Case 2: b2 < approx - delta -> choose left *)
 simpl. right.
 apply Qlt_trans with b2; [exact Hb1_lt_b2 | exact Hcase2].
 
 + destruct (Qlt_le_dec (approx + delta) b2) as [Hcase3 | Hcase3'].
 
 * (* Case 3: approx + delta < b2 -> choose right *)
 simpl. left.
 exact Hcase3.
 
 * (* Case 4: approx + delta >= b2 -> choose left *)
 simpl. right.
 (* Need: b1 < approx - delta *)
 (* Strategy: b1 < b2 - 2*delta <= approx - delta *)
 apply Qlt_le_trans with (b2 - 2 * delta).
 -- (* b1 < b2 - 2*delta *)
 (* This is equivalent to: 2*delta < b2 - b1 = w/3 *)
 (* Which is exactly Hdelta_small *)
 unfold b1, b2, w.
 (* Goal: bis_left s + (bis_right s - bis_left s) / 3 < 
 bis_left s + 2 * (bis_right s - bis_left s) / 3 - 2 * delta *)
 (* Proof by Q-arithmetic transformation *)
 set (l := bis_left s). set (r := bis_right s).
 set (ww := r - l).
 (* l + ww/3 < l + 2*ww/3 - 2*delta *)
 assert (Htwo : ww / 3 + ww / 3 == 2 * ww / 3) by field.
 setoid_replace (l + ww / 3) with (ww / 3 + l) by ring.
 setoid_replace (l + 2 * ww / 3 - 2 * delta) 
 with (2 * ww / 3 - 2 * delta + l) by ring.
 apply (proj2 (Qplus_lt_l (ww / 3) (2 * ww / 3 - 2 * delta) l)).
 setoid_replace (2 * ww / 3 - 2 * delta) with (2 * ww / 3 + (- 2 * delta)) by ring.
 setoid_replace (ww / 3) with (ww / 3 + 2 * delta + (- 2 * delta)) by ring.
 apply (proj2 (Qplus_lt_l (ww / 3 + 2 * delta) (2 * ww / 3) (- 2 * delta))).
 rewrite <- Htwo.
 setoid_replace (ww / 3 + 2 * delta) with (2 * delta + ww / 3) by ring.
 apply (proj2 (Qplus_lt_l (2 * delta) (ww / 3) (ww / 3))).
 exact Hdelta_small.
 -- (* b2 - 2*delta <= approx - delta *)
 (* From Hcase3': b2 <= approx + delta *)
 (* b2 - delta <= approx, then b2 - 2*delta <= approx - delta *)
 assert (H1 : b2 - delta <= approx).
 { apply Qle_minus_compat with (c := delta) in Hcase3'.
 setoid_replace (approx + delta - delta) with approx in Hcase3' by ring.
 exact Hcase3'. }
 apply Qle_minus_compat with (c := delta) in H1.
 setoid_replace (b2 - delta - delta) with (b2 - 2 * delta) in H1 by ring.
 exact H1.
Qed.

(** Trisection iteration with smart choice (OLD - uses 2^n, unsynchronized) *)
Fixpoint trisect_iter_smart (E : Enumeration) (s : BisectionState) (n : nat) : BisectionState :=
 match n with
 | O => s
 | S n' =>
 let s' := trisect_iter_smart E s n' in
 let ref := adaptive_ref n' in
 let approx := E n' ref in
 let delta := 1 / Qpow2 (n' + 5) in (* 1/ref as Q *)
 let choice := smart_trisect_choice s' approx delta in
 trisect_step choice s'
 end.

(* ========================================================================= *)
(* SECTION 12b: SYNCHRONIZED TRISECTION (v2) *)
(* *)
(* MAIN VERSION: This is the FULLY PROVED approach. *)
(* Uses synchronized parameters: delta = 1/(12*3^n), width = 1/3^n *)
(* Guarantees: 2*delta < width/3 for ALL n (no edge cases!) *)
(* ========================================================================= *)

(** 
 KEY INSIGHT: For trisection to work, we need 2*delta < width/3.
 
 After n trisection steps, width = 1/3^n.
 We need: 2*delta < (1/3^n)/3 = 1/3^{n+1}
 
 Solution: Set delta = 1/(12 * 3^n).
 Then: 2*delta = 1/(6*3^n) < 1/(3*3^n) = 1/3^{n+1} 
 
 For regular Cauchy sequences with modulus 1/k at step k,
 we need ref >= 12 * 3^n to ensure error <= delta.
*)

(** Reference index for synchronized trisection *)
Definition trisect_ref (n : nat) : nat := 48 * Pos.to_nat (pow3 n).

(** Delta for synchronized trisection: 1/(24 * 3^n) 
 With ref = 48*3^n, Regular Cauchy bound = 2/ref = 1/(24*3^n) = delta.
 This ensures E_n(m) stays in [approx-delta, approx+delta] for m >= ref,
 while s_{n+1} excludes this confidence interval. *) 
Definition trisect_delta (n : nat) : Q := 1 / (24 * Qpow3 n).

Lemma trisect_delta_pos : forall n, trisect_delta n > 0.
Proof.
 intro n. unfold trisect_delta.
 apply Qlt_shift_div_l.
 - apply Qmult_lt_0_compat.
 + unfold Qlt; simpl; lia.
 + apply Qpow3_pos.
 - ring_simplify. unfold Qlt; simpl; lia.
Qed.

(** w/3 > 6*delta for our synchronized parameters *)
Lemma third_width_gt_6_delta : forall n,
 (1 / Qpow3 n) / 3 > 6 * trisect_delta n.
Proof.
 intro n. unfold trisect_delta, Qlt, Qdiv, Qmult, Qinv. simpl. lia.
Qed.

(** If gap > w/3, then gap > 6*delta *)
Lemma gap_gt_third_implies_gt_6delta : forall gap n,
 gap > (1 / Qpow3 n) / 3 ->
 gap > 6 * trisect_delta n.
Proof.
 intros gap n Hgap.
 apply Qlt_trans with ((1 / Qpow3 n) / 3).
 - apply third_width_gt_6_delta.
 - exact Hgap.
Qed.

(** If gap > w/3, then gap >= 6*delta (weaker but useful) *)
Lemma gap_gt_third_implies_ge_6delta : forall gap n,
 gap > (1 / Qpow3 n) / 3 ->
 gap >= 6 * trisect_delta n.
Proof.
 intros gap n Hgap.
 apply Qlt_le_weak.
 apply gap_gt_third_implies_gt_6delta. exact Hgap.
Qed.

(** Synchronized trisection iteration *)
Fixpoint trisect_iter_v2 (E : Enumeration) (s : BisectionState) (n : nat) : BisectionState :=
 match n with
 | O => s
 | S n' =>
 let s' := trisect_iter_v2 E s n' in
 let ref := trisect_ref n' in
 let approx := E n' ref in
 let delta := trisect_delta n' in
 let choice := smart_trisect_choice s' approx delta in
 trisect_step choice s'
 end.

(** Width after n trisection steps *)
Lemma trisect_iter_v2_width : forall E n,
 let s := trisect_iter_v2 E (mkBisection 0 1) n in
 bis_right s - bis_left s == 1 / Qpow3 n.
Proof.
 intros E n.
 induction n.
 - (* Base: width = 1 - 0 = 1 = 1/3^0 *)
 simpl. unfold Qpow3. simpl. field.
 - (* Step: width shrinks by factor 3 *)
 simpl trisect_iter_v2.
 set (s' := trisect_iter_v2 E (mkBisection 0 1) n) in *.
 set (choice := smart_trisect_choice s' (E n (trisect_ref n)) (trisect_delta n)).
 (* trisect_step choice s' has width = width(s') / 3 *)
 unfold trisect_step.
 destruct choice.
 + (* TrisectLeft *)
 rewrite trisect_left_width.
 rewrite IHn.
 rewrite Qpow3_triple.
 field.
 intro H. unfold Qeq, Qpow3 in H. simpl in H. lia.
 + (* TrisectMiddle *)
 rewrite trisect_middle_width.
 rewrite IHn.
 rewrite Qpow3_triple.
 field.
 intro H. unfold Qeq, Qpow3 in H. simpl in H. lia.
 + (* TrisectRight *)
 rewrite trisect_right_width.
 rewrite IHn.
 rewrite Qpow3_triple.
 field.
 intro H. unfold Qeq, Qpow3 in H. simpl in H. lia.
Qed.

(** Validity: left <= right after any number of steps *)
Lemma trisect_iter_v2_valid : forall E n,
 let s := trisect_iter_v2 E (mkBisection 0 1) n in
 bis_left s <= bis_right s.
Proof.
 intros E n.
 induction n.
 - simpl. unfold Qle; simpl; lia.
 - simpl trisect_iter_v2.
 set (s' := trisect_iter_v2 E (mkBisection 0 1) n) in *.
 set (choice := smart_trisect_choice s' (E n (trisect_ref n)) (trisect_delta n)).
 unfold trisect_step.
 destruct choice.
 + apply trisect_left_valid. exact IHn.
 + apply trisect_middle_valid. exact IHn.
 + apply trisect_right_valid. exact IHn.
Qed.

(** Nested interval property: later intervals are contained in earlier ones *)
Lemma trisect_iter_v2_nested : forall E k m,
 (k <= m)%nat ->
 let s_k := trisect_iter_v2 E (mkBisection 0 1) k in
 let s_m := trisect_iter_v2 E (mkBisection 0 1) m in
 bis_left s_k <= bis_left s_m /\ bis_right s_m <= bis_right s_k.
Proof.
 intros E k m Hkm.
 induction Hkm.
 - (* k = m *) simpl. split; apply Qle_refl.
 - (* k <= m -> k <= S m *)
 (* IHHkm: s_k nested in s_m *)
 (* Need: s_k nested in s_{S m} = trisect_step choice s_m *)
 simpl.
 set (s_m := trisect_iter_v2 E (mkBisection 0 1) m) in *.
 set (choice := smart_trisect_choice s_m (E m (trisect_ref m)) (trisect_delta m)).
 
 (* s_m is valid *)
 assert (Hvalid : bis_left s_m <= bis_right s_m).
 { apply trisect_iter_v2_valid. }
 
 (* trisect_step produces nested subinterval *)
 pose proof (trisect_step_nested choice s_m Hvalid) as [Hstep_l Hstep_r].
 
 (* Combine with IH *)
 destruct IHHkm as [IHl IHr].
 split.
 + (* bis_left s_k <= bis_left (trisect_step choice s_m) *)
 apply Qle_trans with (bis_left s_m).
 * exact IHl.
 * exact Hstep_l.
 + (* bis_right (trisect_step choice s_m) <= bis_right s_k *)
 apply Qle_trans with (bis_right s_m).
 * exact Hstep_r.
 * exact IHr.
Qed.

(** The synchronized trisection-based diagonal process (v2) 
 MOVED HERE to be available for diagonal_v2_in_interval *)
Definition diagonal_trisect_v2 (E : Enumeration) : RealProcess :=
 fun n => (bis_left (trisect_iter_v2 E (mkBisection 0 1) n) + 
 bis_right (trisect_iter_v2 E (mkBisection 0 1) n)) / 2.

(** Diagonal v2 is within interval_k for any k <= m *)
Lemma diagonal_v2_in_interval : forall E k m,
 (k <= m)%nat ->
 let s_k := trisect_iter_v2 E (mkBisection 0 1) k in
 bis_left s_k <= diagonal_trisect_v2 E m /\ diagonal_trisect_v2 E m <= bis_right s_k.
Proof.
 intros E k m Hkm.
 unfold diagonal_trisect_v2.
 set (s_k := trisect_iter_v2 E (mkBisection 0 1) k).
 set (s_m := trisect_iter_v2 E (mkBisection 0 1) m).
 
 pose proof (trisect_iter_v2_nested E k m Hkm) as [Hl Hr].
 pose proof (trisect_iter_v2_valid E m) as Hvalid_m.
 
 fold s_k s_m in Hl, Hr.
 fold s_m in Hvalid_m.
 
 split.
 - (* bis_left s_k <= midpoint(s_m) *)
 (* bis_left s_k <= bis_left s_m <= midpoint(s_m) *)
 apply Qle_trans with (bis_left s_m).
 + exact Hl.
 + apply midpoint_ge_left. exact Hvalid_m.
 - (* midpoint(s_m) <= bis_right s_k *)
 (* midpoint(s_m) <= bis_right s_m <= bis_right s_k *)
 apply Qle_trans with (bis_right s_m).
 + apply midpoint_le_right. exact Hvalid_m.
 + exact Hr.
Qed.

(** Connection between trisect_ref and trisect_delta 
 With ref = 48*3^n and delta = 1/(24*3^n), we have delta = 2/ref.
 This means Regular Cauchy bound 2/ref = delta. *)
Lemma trisect_ref_delta_relation : forall n,
 trisect_delta n == 2 / inject_Z (Z.of_nat (trisect_ref n)).
Proof.
 intro n.
 unfold trisect_delta, trisect_ref, Qpow3, inject_Z.
 rewrite Nat2Z.inj_mul.
 rewrite positive_nat_Z.
 unfold Qeq, Qdiv, Qmult, Qinv. simpl. lia.
Qed.

(** Helper: 1/m <= 1/ref when m >= ref *)
Lemma inv_le : forall m ref : nat,
 (ref <= m)%nat -> (ref > 0)%nat ->
 (1 # Pos.of_nat m) <= (1 # Pos.of_nat ref).
Proof.
 intros m ref Hm Href_pos.
 assert (Hm_pos : (m > 0)%nat) by lia.
 unfold Qle. simpl.
 intro Hcontra.
 apply Z.compare_gt_iff in Hcontra.
 assert (Hlt : (Z.pos (Pos.of_nat m) < Z.pos (Pos.of_nat ref))%Z) by lia.
 apply Pos2Z.pos_lt_pos in Hlt.
 apply Pos2Nat.inj_lt in Hlt.
 rewrite !Nat2Pos.id in Hlt by lia.
 lia.
Qed.

(** Helper: 2#pos = 2/Z.pos pos *)
Lemma two_over_ref : forall ref : nat, (ref > 0)%nat ->
 (2 # Pos.of_nat ref) == 2 / inject_Z (Z.of_nat ref).
Proof.
 intros ref Hpos.
 destruct ref as [|ref'].
 - lia.
 - unfold inject_Z. simpl Z.of_nat.
 unfold Qdiv, Qmult, Qinv. simpl.
 destruct ref' as [|ref''].
 + simpl. reflexivity.
 + simpl. rewrite Pos.of_nat_succ. reflexivity.
Qed.

(** Regular Cauchy bound using trisect_ref *)
Lemma regular_Cauchy_with_trisect_ref : forall E n m,
 valid_regular_enumeration E ->
 (trisect_ref n <= m)%nat ->
 Qabs (E n m - E n (trisect_ref n)) <= trisect_delta n.
Proof.
 intros E n m Hvalid Hm.
 destruct (Hvalid n) as [Hreg Hbounds].
 unfold is_Regular_Cauchy in Hreg.
 
 set (ref := trisect_ref n).
 
 assert (Href_pos : (ref > 0)%nat).
 { unfold ref, trisect_ref. 
 pose proof (pow3_pos n). lia. }
 
 assert (Hm_pos : (m > 0)%nat) by lia.
 
 specialize (Hreg m ref Hm_pos Href_pos).
 
 apply Qle_trans with ((1 # Pos.of_nat m) + (1 # Pos.of_nat ref)).
 - exact Hreg.
 - apply Qle_trans with ((1 # Pos.of_nat ref) + (1 # Pos.of_nat ref)).
 + apply Qplus_le_compat.
 * apply inv_le; assumption.
 * apply Qle_refl.
 + (* 2 * (1/ref) = 2/ref = delta *)
 assert (Heq : (1 # Pos.of_nat ref) + (1 # Pos.of_nat ref) == 
 (2 # Pos.of_nat ref)).
 { unfold Qplus, Qeq. simpl. lia. }
 rewrite Heq.
 (* Now: 2 # Pos.of_nat ref <= trisect_delta n *)
 (* ref = trisect_ref n, so we need 2#Pos.of_nat(trisect_ref n) <= delta n *)
 (* By two_over_ref: 2#Pos.of_nat(ref) == 2/inject_Z(Z.of_nat ref) *)
 (* By trisect_ref_delta_relation: delta n == 2/inject_Z(Z.of_nat(trisect_ref n)) *)
 unfold ref.
 apply Qle_trans with (2 / inject_Z (Z.of_nat (trisect_ref n))).
 * apply Qle_lteq. right. apply two_over_ref.
 unfold trisect_ref. pose proof (pow3_pos n). lia.
 * apply Qle_lteq. right. symmetry. apply trisect_ref_delta_relation.
Qed.

(** Helper: Pos.of_nat preserves strict order *)
Lemma Pos_of_nat_lt : forall m ref : nat,
 (ref < m)%nat -> (0 < ref)%nat ->
 (Pos.of_nat ref < Pos.of_nat m)%positive.
Proof.
 intros m ref Hlt Href_pos.
 assert (Hm_pos : (0 < m)%nat) by lia.
 rewrite <- (Nat2Pos.id ref) by lia.
 rewrite <- (Nat2Pos.id m) by lia.
 apply Pos2Nat.inj_lt.
 rewrite !Nat2Pos.id by lia.
 exact Hlt.
Qed.

(** Helper: 1/m < 1/ref when m > ref *)
Lemma one_over_lt : forall m ref : nat,
 (ref < m)%nat -> (0 < ref)%nat ->
 (1 # Pos.of_nat m) < (1 # Pos.of_nat ref).
Proof.
 intros m ref Hlt Href_pos.
 unfold Qlt. simpl.
 apply Pos2Z.pos_lt_pos.
 apply Pos_of_nat_lt; assumption.
Qed.

(** Helper: 1/m + 1/ref < 2/ref when m > ref *)
Lemma sum_lt_double : forall m ref : nat,
 (ref < m)%nat -> (0 < ref)%nat ->
 (1 # Pos.of_nat m) + (1 # Pos.of_nat ref) < 2 * (1 # Pos.of_nat ref).
Proof.
 intros m ref Hlt Href_pos.
 pose proof (one_over_lt m ref Hlt Href_pos) as H1m.
 setoid_replace (2 * (1 # Pos.of_nat ref)) 
 with ((1 # Pos.of_nat ref) + (1 # Pos.of_nat ref)) by ring.
 apply Qplus_lt_l.
 exact H1m.
Qed.

(** trisect_ref is always positive *)
Lemma trisect_ref_pos : forall n, (0 < trisect_ref n)%nat.
Proof.
 intro n. unfold trisect_ref. 
 assert (Hpow3_pos : (0 < Pos.to_nat (pow3 n))%nat).
 { apply Pos2Nat.is_pos. }
 lia.
Qed.

(** For m > ref, Regular Cauchy gives |E_n(m) - approx| < delta *)
Lemma regular_Cauchy_strict : forall E n m,
 valid_regular_enumeration E ->
 (trisect_ref n < m)%nat ->
 Qabs (E n m - E n (trisect_ref n)) < trisect_delta n.
Proof.
 intros E n m Hvalid Hm.
 (* From is_Regular_Cauchy: |E_n(m) - E_n(ref)| <= 1/m + 1/ref *)
 destruct (Hvalid n) as [HEn_reg _].
 assert (Hm_pos : (m > 0)%nat) by lia.
 pose proof (trisect_ref_pos n) as Href_pos.
 specialize (HEn_reg m (trisect_ref n) Hm_pos Href_pos).
 
 (* HEn_reg: |E_n(m) - E_n(ref)| <= 1/m + 1/ref *)
 (* We need: |...| < delta = 2/ref *)
 apply Qle_lt_trans with ((1 # Pos.of_nat m) + (1 # Pos.of_nat (trisect_ref n))).
 - exact HEn_reg.
 - (* 1/m + 1/ref < 2/ref = delta *)
 pose proof (sum_lt_double m (trisect_ref n) Hm Href_pos) as Hsum.
 (* Hsum: 1/m + 1/ref < 2 * (1/ref) *)
 (* Need to show: 2 * (1/ref) <= delta = 2/ref *)
 (* Actually 2 * (1 # ref) == 2 # ref, and delta = 2/ref *)
 pose proof (trisect_ref_delta_relation n) as Hdelta.
 (* Hdelta: delta == 2 / inject_Z (Z.of_nat ref) *)
 (* 2 * (1 # ref) = 2 / ref *)
 setoid_rewrite Hdelta.
 (* Goal: 1/m + 1/ref < 2 / inject_Z (Z.of_nat (trisect_ref n)) *)
 (* Hsum: 1/m + 1/ref < 2 * (1 # Pos.of_nat (trisect_ref n)) *)
 (* Need: 2 * (1 # Pos.of_nat ref) == 2 / inject_Z (Z.of_nat ref) *)
 assert (Heq : 2 * (1 # Pos.of_nat (trisect_ref n)) == 
 2 / inject_Z (Z.of_nat (trisect_ref n))).
 { unfold inject_Z, Qdiv, Qmult, Qinv.
 unfold Qeq. simpl.
 destruct (Z.of_nat (trisect_ref n)) eqn:Hz.
 - exfalso. lia.
 - simpl. lia.
 - exfalso. lia. }
 setoid_rewrite <- Heq.
 exact Hsum.
Qed.

(** Interval bounds in [0,1] *)
Lemma trisect_iter_v2_in_unit : forall E n,
 let s := trisect_iter_v2 E (mkBisection 0 1) n in
 0 <= bis_left s /\ bis_right s <= 1.
Proof.
 intros E n.
 induction n.
 - simpl. split; unfold Qle; simpl; lia.
 - simpl.
 set (s' := trisect_iter_v2 E (mkBisection 0 1) n) in *.
 destruct IHn as [H0l Hr1].
 pose proof (trisect_iter_v2_valid E n) as Hvalid.
 fold s' in Hvalid, H0l, Hr1.
 unfold trisect_step.
 destruct (smart_trisect_choice s' (E n (trisect_ref n)) (trisect_delta n)).
 + (* TrisectLeft *)
 simpl. split.
 * exact H0l.
 * apply Qle_trans with (bis_right s').
 -- (* l + w/3 <= r *)
 setoid_replace (bis_left s' + (bis_right s' - bis_left s') / 3)
 with (bis_left s' * (2/3) + bis_right s' * (1/3)) by field.
 apply Qle_trans with (bis_right s' * (2/3) + bis_right s' * (1/3)).
 ++ apply Qplus_le_compat.
 ** apply Qmult_le_compat_r; [exact Hvalid | unfold Qle; simpl; lia].
 ** apply Qle_refl.
 ++ setoid_replace (bis_right s' * (2/3) + bis_right s' * (1/3)) 
 with (bis_right s') by field.
 apply Qle_refl.
 -- exact Hr1.
 + (* TrisectMiddle *)
 simpl. split.
 * apply Qle_trans with (bis_left s').
 -- exact H0l.
 -- apply Qle_trans with (bis_left s' + 0).
 ++ ring_simplify. apply Qle_refl.
 ++ apply Qplus_le_compat. apply Qle_refl.
 apply Qdiv3_nonneg. apply Qminus_nonneg. exact Hvalid.
 * apply Qle_trans with (bis_right s').
 -- setoid_replace (bis_left s' + 2 * (bis_right s' - bis_left s') / 3)
 with (bis_left s' * (1/3) + bis_right s' * (2/3)) by field.
 apply Qle_trans with (bis_right s' * (1/3) + bis_right s' * (2/3)).
 ++ apply Qplus_le_compat.
 ** apply Qmult_le_compat_r; [exact Hvalid | unfold Qle; simpl; lia].
 ** apply Qle_refl.
 ++ setoid_replace (bis_right s' * (1/3) + bis_right s' * (2/3))
 with (bis_right s') by field.
 apply Qle_refl.
 -- exact Hr1.
 + (* TrisectRight *)
 simpl. split.
 * apply Qle_trans with (bis_left s').
 -- exact H0l.
 -- apply Qle_trans with (bis_left s' + 0).
 ++ ring_simplify. apply Qle_refl.
 ++ apply Qplus_le_compat. apply Qle_refl.
 unfold Qdiv. apply Qmult_le_0_compat.
 ** apply Qmult_le_0_compat.
 --- unfold Qle; simpl; lia.
 --- apply Qminus_nonneg. exact Hvalid.
 ** unfold Qle; simpl; lia.
 * exact Hr1.
Qed.

(** The trisection-based diagonal process (OLD VERSION) *)
Definition diagonal_trisect (E : Enumeration) : RealProcess :=
 fun n => (bis_left (trisect_iter_smart E (mkBisection 0 1) n) + 
 bis_right (trisect_iter_smart E (mkBisection 0 1) n)) / 2.

(** MAIN LEMMA: Synchronized trisection GUARANTEES exclusion.
 
 This is the heart of the proof: at each step n, the confidence interval
 [approx - delta, approx + delta] is COMPLETELY excluded from interval_{n+1}.
 
 Unlike bisection (which can have boundary issues), trisection with 
 synchronized delta = 1/(12*3^n) ALWAYS satisfies 2*delta < width/3.
*)
Lemma regular_excluded_by_trisection_v2 : forall E n,
 valid_regular_enumeration E ->
 let s_n := trisect_iter_v2 E (mkBisection 0 1) n in
 let s_n1 := trisect_iter_v2 E (mkBisection 0 1) (S n) in
 let approx := E n (trisect_ref n) in
 let delta := trisect_delta n in
 (* The entire confidence interval is excluded from s_n1 *)
 (approx + delta < bis_left s_n1) \/ (bis_right s_n1 < approx - delta).
Proof.
 intros E n Hvalid.
 simpl.
 set (s_n := trisect_iter_v2 E (mkBisection 0 1) n).
 set (approx := E n (trisect_ref n)).
 set (delta := trisect_delta n).
 
 (* The next interval is obtained by smart_trisect_choice *)
 (* s_n1 = trisect_step (smart_trisect_choice s_n approx delta) s_n *)
 
 (* Apply smart_choice_excludes_confidence *)
 pose proof (smart_choice_excludes_confidence s_n approx delta) as Hexcl.
 
 (* Check preconditions *)
 assert (Hs_valid : bis_left s_n <= bis_right s_n).
 { apply trisect_iter_v2_valid. }
 
 assert (Hdelta_pos : delta > 0).
 { apply trisect_delta_pos. }
 
 assert (Hdelta_small : 2 * delta < (bis_right s_n - bis_left s_n) / 3).
 {
 (* width = 1/3^n by trisect_iter_v2_width *)
 pose proof (trisect_iter_v2_width E n) as Hwidth.
 simpl in Hwidth. fold s_n in Hwidth.
 
 (* delta = 1/(12*3^n) *)
 (* 2*delta = 2/(12*3^n) = 1/(6*3^n) *)
 (* width/3 = (1/3^n)/3 = 1/(3*3^n) = 1/3^{n+1} *)
 (* Need: 1/(6*3^n) < 1/(3*3^n), i.e., 3 < 6 *)
 
 (* Rewrite width using Hwidth *)
 setoid_replace (bis_right s_n - bis_left s_n) with (1 / Qpow3 n) by exact Hwidth.
 
 (* Now apply trisect_delta_bound *)
 unfold delta, trisect_delta.
 apply trisect_delta_bound.
 }
 
 specialize (Hexcl Hs_valid Hdelta_pos Hdelta_small).
 
 (* Hexcl gives us exactly what we need *)
 exact Hexcl.
Qed.


(* ========================================================================= *)
(* SECTION 12c: COMPLETE TRISECTION THEOREM (v2) - FULLY PROVED *)
(* *)
(* MAIN THEOREM: unit_interval_uncountable_trisect_v2 *)
(* ALL dependencies are Qed. No Admitted in dependency tree. *)
(* ========================================================================= *)

(** Diagonal v2 is Cauchy: intervals shrink by 1/3 each step *)
Lemma diagonal_trisect_v2_is_Cauchy : forall E,
 is_Cauchy (diagonal_trisect_v2 E).
Proof.
 intro E.
 unfold is_Cauchy.
 intros eps Heps.
 
 (* For any eps > 0, find N such that 1/3^N < eps *)
 destruct (Archimedean_pow3 eps Heps) as [N HN].
 exists N.
 intros m n Hm Hn.
 
 (* Let k = min(m, n) >= N *)
 set (k := Nat.min m n).
 assert (Hkm : (k <= m)%nat) by (unfold k; apply Nat.le_min_l).
 assert (Hkn : (k <= n)%nat) by (unfold k; apply Nat.le_min_r).
 (* Hm: m > N means N < m, so N <= m *)
 (* Hn: n > N means N < n, so N <= n *)
 assert (Hm' : (N <= m)%nat) by lia.
 assert (Hn' : (N <= n)%nat) by lia.
 assert (HkN : (N <= k)%nat) by (unfold k; apply Nat.min_glb; [exact Hm' | exact Hn']).
 
 (* D(m) and D(n) both lie in interval_k *)
 pose proof (diagonal_v2_in_interval E k m Hkm) as [Hlm Hrm].
 pose proof (diagonal_v2_in_interval E k n Hkn) as [Hln Hrn].
 simpl in Hlm, Hrm, Hln, Hrn.
 
 set (s_k := trisect_iter_v2 E (mkBisection 0 1) k) in *.
 
 (* |D(m) - D(n)| <= width(interval_k) *)
 apply Qle_lt_trans with (bis_right s_k - bis_left s_k).
 - (* |D(m) - D(n)| <= r_k - l_k *)
 apply interval_diameter_bound.
 + split; assumption.
 + split; assumption.
 - (* r_k - l_k < eps *)
 (* width(interval_k) = 1/3^k *)
 pose proof (trisect_iter_v2_width E k) as Hwidth.
 simpl in Hwidth. fold s_k in Hwidth.
 (* Hwidth: bis_right s_k - bis_left s_k == 1 / Qpow3 k *)
 
 (* 1/3^k <= 1/3^N < eps *)
 apply Qle_lt_trans with (1 / Qpow3 N).
 + (* 1/3^k <= 1/3^N *)
 setoid_rewrite Hwidth.
 apply Qpow3_inv_mono. exact HkN.
 + (* 1/3^N < eps *)
 exact HN.
Qed.

(** Diagonal v2 is in [0,1] *)
Lemma diagonal_trisect_v2_in_unit : forall E n,
 0 <= diagonal_trisect_v2 E n <= 1.
Proof.
 intros E n.
 unfold diagonal_trisect_v2.
 set (s := trisect_iter_v2 E (mkBisection 0 1) n).
 pose proof (trisect_iter_v2_in_unit E n) as [H0l Hr1].
 simpl in H0l, Hr1. fold s in H0l, Hr1.
 pose proof (trisect_iter_v2_valid E n) as Hvalid.
 fold s in Hvalid.
 split.
 - apply Qle_trans with (bis_left s).
 + exact H0l.
 + apply midpoint_ge_left. exact Hvalid.
 - apply Qle_trans with (bis_right s).
 + apply midpoint_le_right. exact Hvalid.
 + exact Hr1.
Qed.

(** CRITICAL: Minimum gap = w/3 - 2*delta = 6*delta.
 When confidence interval doesn't intersect chosen third,
 gap >= width/3 - 2*delta because:
 - width/3 is the size of each third
 - 2*delta is the size of confidence interval 
 - In the worst case, confidence just touches the boundary *)
Lemma min_gap_eq_6_delta : forall n,
 (1 / Qpow3 n) / 3 - 2 * trisect_delta n == 6 * trisect_delta n.
Proof.
 intro n.
 unfold trisect_delta.
 field.
 apply Qpow3_neq0.
Qed.


(** KEY LEMMA: For regular sequences, diagonal v2 differs from each E_n.
 SIMPLE PROOF using gap/2 as epsilon. *)

Lemma diagonal_trisect_v2_differs_from_E_n : forall E n,
 valid_regular_enumeration E ->
 not_equiv (diagonal_trisect_v2 E) (E n).
Proof.
 intros E n Hvalid.
 unfold not_equiv.
 
 (* Use the exclusion lemma *)
 pose proof (regular_excluded_by_trisection_v2 E n Hvalid) as Hexcl.
 simpl in Hexcl.
 
 (* After simpl, s_n1 expands to trisect_step ... *)
 set (s_n := trisect_iter_v2 E (mkBisection 0 1) n) in *.
 set (approx := E n (trisect_ref n)) in *.
 set (delta := trisect_delta n) in *.
 set (s_n1 := trisect_step (smart_trisect_choice s_n approx delta) s_n) in *.
 
 (* The gap between confidence interval and chosen interval *)
 destruct Hexcl as [Hleft | Hright].
 
 - (* Case: approx + delta < bis_left s_n1 *)
 set (gap := bis_left s_n1 - (approx + delta)).
 assert (Hgap_pos : gap > 0).
 { unfold gap.
 apply Qlt_minus_iff in Hleft.
 setoid_replace (bis_left s_n1 - (approx + delta)) 
 with (bis_left s_n1 + - (approx + delta)) by ring.
 exact Hleft. }
 
 exists (gap / 2).
 split.
 + (* gap/2 > 0 *)
 apply Qlt_shift_div_l.
 * unfold Qlt; simpl; lia.
 * ring_simplify. exact Hgap_pos.
 + intro N.
 set (ref := trisect_ref n).
 exists (S (Nat.max N (Nat.max ref (S n)))).
 split.
 * lia.
 * set (m := S (Nat.max N (Nat.max ref (S n)))).
 
 (* D(m) >= bis_left s_n1 *)
 assert (Hd_in : bis_left s_n1 <= diagonal_trisect_v2 E m).
 { assert (Hm_ge : (S n <= m)%nat) by (unfold m; lia).
 pose proof (diagonal_v2_in_interval E (S n) m Hm_ge) as [Hl _].
 exact Hl. }
 
 (* E_n(m) <= approx + delta *)
 assert (He_conf : E n m <= approx + delta).
 { assert (Hm_ge_ref : (ref <= m)%nat) by (unfold m, ref; lia).
 pose proof (regular_Cauchy_with_trisect_ref E n m Hvalid Hm_ge_ref) as Hbound.
 apply Qabs_Qle_condition in Hbound.
 destruct Hbound as [_ Hright_bound].
 (* Hright_bound: E n m - E n (trisect_ref n) <= delta *)
 (* Need: E n m <= approx + delta = E n (trisect_ref n) + delta *)
 unfold approx.
 setoid_replace (E n m) with ((E n m - E n (trisect_ref n)) + E n (trisect_ref n)) by ring.
 setoid_replace (E n (trisect_ref n) + delta) with (delta + E n (trisect_ref n)) by ring.
 apply Qplus_le_compat.
 - exact Hright_bound.
 - apply Qle_refl. }
 
 (* D(m) - E_n(m) >= gap *)
 assert (Hdiff : diagonal_trisect_v2 E m - E n m >= gap).
 { unfold gap.
 apply Qplus_le_compat.
 - exact Hd_in.
 - apply Qopp_le_compat. exact He_conf. }
 
 apply Qle_trans with gap.
 -- apply Qlt_le_weak.
 (* gap/2 < gap *)
 unfold Qdiv, Qlt in *.
 destruct gap as [gn gd]. simpl in *.
 lia.
 -- apply Qle_trans with (diagonal_trisect_v2 E m - E n m).
 ++ exact Hdiff.
 ++ apply Qle_Qabs.
 
 - (* Case: bis_right s_n1 < approx - delta (symmetric) *)
 set (gap := (approx - delta) - bis_right s_n1).
 assert (Hgap_pos : gap > 0).
 { unfold gap.
 apply Qlt_minus_iff in Hright.
 setoid_replace ((approx - delta) - bis_right s_n1)
 with ((approx - delta) + - bis_right s_n1) by ring.
 exact Hright. }
 
 exists (gap / 2).
 split.
 + apply Qlt_shift_div_l.
 * unfold Qlt; simpl; lia.
 * ring_simplify. exact Hgap_pos.
 + intro N.
 set (ref := trisect_ref n).
 exists (S (Nat.max N (Nat.max ref (S n)))).
 split.
 * lia.
 * set (m := S (Nat.max N (Nat.max ref (S n)))).
 
 (* D(m) <= bis_right s_n1 *)
 assert (Hd_in : diagonal_trisect_v2 E m <= bis_right s_n1).
 { assert (Hm_ge : (S n <= m)%nat) by (unfold m; lia).
 pose proof (diagonal_v2_in_interval E (S n) m Hm_ge) as [_ Hr].
 exact Hr. }
 
 (* E_n(m) >= approx - delta *)
 assert (He_conf : approx - delta <= E n m).
 { assert (Hm_ge_ref : (ref <= m)%nat) by (unfold m, ref; lia).
 pose proof (regular_Cauchy_with_trisect_ref E n m Hvalid Hm_ge_ref) as Hbound.
 apply Qabs_Qle_condition in Hbound.
 destruct Hbound as [Hleft_bound _].
 (* Hleft_bound: -delta <= E n m - approx *)
 (* Need: approx - delta <= E n m *)
 (* Equivalently: -delta + approx <= E n m, i.e., -delta <= E n m - approx *)
 unfold approx.
 setoid_replace (E n (trisect_ref n) - delta) with (-delta + E n (trisect_ref n)) by ring.
 setoid_replace (E n m) with ((E n m - E n (trisect_ref n)) + E n (trisect_ref n)) by ring.
 apply Qplus_le_compat.
 - exact Hleft_bound.
 - apply Qle_refl. }
 
 (* E_n(m) - D(m) >= gap *)
 assert (Hdiff : E n m - diagonal_trisect_v2 E m >= gap).
 { unfold gap.
 apply Qplus_le_compat.
 - exact He_conf.
 - apply Qopp_le_compat. exact Hd_in. }
 
 apply Qle_trans with gap.
 -- apply Qlt_le_weak.
 (* gap/2 < gap *)
 unfold Qdiv, Qlt in *.
 destruct gap as [gn gd]. simpl in *.
 lia.
 -- apply Qle_trans with (E n m - diagonal_trisect_v2 E m).
 ++ exact Hdiff.
 ++ rewrite Qabs_Qminus. apply Qle_Qabs.
Qed.


(** ================================================================== *)
(** MAIN THEOREM v2: [0,1] is uncountable (FULLY PROVED modulo technicals) *)
(** ================================================================== *)

Theorem unit_interval_uncountable_trisect_v2 : forall E : Enumeration,
 valid_regular_enumeration E ->
 exists D : RealProcess,
 is_Cauchy D /\ 
 (forall m, 0 <= D m <= 1) /\ 
 (forall n, not_equiv D (E n)).
Proof.
 intros E Hvalid.
 exists (diagonal_trisect_v2 E).
 split; [| split].
 - apply diagonal_trisect_v2_is_Cauchy.
 - intro m. apply diagonal_trisect_v2_in_unit.
 - intro n. apply diagonal_trisect_v2_differs_from_E_n. exact Hvalid.
Qed.

(* ========================================================================= *)
(* SECTION 13: VERIFICATION AND SUMMARY *)
(* ========================================================================= *)

Print Assumptions shrinking_interval_Cauchy.
Print Assumptions bisect_width_n.

(** 
 SUMMARY OF THE PROOF (Updated January 2026)
 ============================================
 
 MAIN THEOREM: unit_interval_uncountable_trisect_v2 (FULLY PROVED)
 
 For REGULAR Cauchy sequences (with known convergence rate 1/m):
 - Uses TRISECTION with synchronized parameters:
 * ref = 12 * 3^n
 * delta = 1/(12 * 3^n)
 * width = 1/3^n
 - Key guarantee: 2*delta < width/3 ALWAYS
 - NO edge cases ~ trisection eliminates boundary problems geometrically
 - ALL dependencies are Qed (no Admitted in dependency tree)
 
 PHILOSOPHICAL SIGNIFICANCE:
 
 The trisection construction embodies the Theory of Systems principles:
 
 P4 (Finitude): Each step is finite, decidable ~ no completed infinities
 L3 (Excluded Middle): Trisection choice is deterministic 
 L4 (Sufficient Reason): Gap has quantitative cause (2 < w/3)
 L5 (Order): Hierarchical construction, each level depends on previous
 
 KEY INSIGHT:
 - Bisection fails at boundaries ~ enemy can be exactly at midpoint
 - Trisection ALWAYS works ~ enemy occupies at most 1/3, leaving 2/3 free
 - Synchronized delta ensures 2*delta < width/3 for ALL n
 
 DEPENDENCIES:
 - Classic: Used for excluded middle (derivable from L3)
 - Axiom of Infinity: NOT USED (reals are processes, not completed sets)
 - Axiom of Choice: NOT USED (trisection is deterministic)
 
 Everything is derived from:
 - Q-arithmetic (decidable, constructive)
 - Natural number induction (P4-compatible: finite at each step)
 - Archimedean property (theorem, not axiom)
 - Powers of 3 (for trisection width tracking)
*)

Print Assumptions unit_interval_uncountable_trisect_v2.
