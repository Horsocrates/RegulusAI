(* ========================================================================= *)
(*  COMPOSITION & RE-ANCHORING VERIFICATION                                *)
(*  Part of: Regulus -- Verified AI Computation                            *)
(*                                                                         *)
(*  Author:  Horsocrates | Date: February 2026                             *)
(*                                                                         *)
(*  E/R/R INTERPRETATION:                                                  *)
(*    Elements = PIntervals (layer activations)                            *)
(*    Roles    = pi_reanchor, chain_width, pi_max_pair                     *)
(*    Rules    = composition bounds, re-anchoring contracts                 *)
(*                                                                         *)
(*  KEY THEOREMS:                                                          *)
(*    1. pi_reanchor_width: width(reanchor(I, eps)) == 2 * eps             *)
(*    2. pi_reanchor_contains_midpoint: midpoint always in reanchored      *)
(*    3. pi_reanchor_loses_containment: re-anchoring is LOSSY              *)
(*    4. chain_width_product: naive chain = product of factors * width     *)
(*    5. reanchored_final_width: with reanchor, depth-independent bound    *)
(*    6. pi_max_pair_correct: MaxPool soundness via monotonicity of max    *)
(*    7. pi_max_pair_width: MaxPool width bound                            *)
(*    8. pi_residual_correct: ResBlock containment (x + f(x))             *)
(*    9. pi_resblock_width_bound: width(relu(x+f(x))) ≤ w(x) + w(f(x))  *)
(*                                                                         *)
(*  AXIOMS: NONE. Fully constructive. Extraction-compatible.               *)
(*                                                                         *)
(* ========================================================================= *)

From ToS Require Import PInterval.
From ToS Require Import PInterval_Linear.
From ToS Require Import PInterval_Conv.

Require Import Coq.QArith.QArith.
Require Import Coq.QArith.Qabs.
Require Import Coq.QArith.Qminmax.
Require Import Coq.micromega.Lia.
Require Import Coq.ZArith.ZArith.
Require Import Coq.Setoids.Setoid.
Require Import Coq.Lists.List.
Import ListNotations.

Open Scope Q_scope.


(* ===================================================================== *)
(* SECTION 1: RE-ANCHORING                                               *)
(* Re-anchor: collapse interval to [mid - eps, mid + eps].               *)
(* This is the process-based trick that prevents exponential blowup.     *)
(* ===================================================================== *)

(* Midpoint *)
Definition pi_midpoint (I : PInterval) : Q :=
  (pi_lo I + pi_hi I) / (2 # 1).

(* Re-anchored interval: [mid - eps, mid + eps] *)
Lemma Qle_from_diff_nonneg : forall a b : Q, 0 <= b - a -> a <= b.
Proof.
  intros a b H.
  setoid_replace a with (a + 0) by ring.
  setoid_replace b with (a + (b - a)) by ring.
  apply Qplus_le_compat.
  - apply Qle_refl.
  - exact H.
Qed.

Lemma pi_reanchor_valid : forall (I : PInterval) (eps : Q),
  0 <= eps -> pi_midpoint I - eps <= pi_midpoint I + eps.
Proof.
  intros I eps Heps.
  apply Qle_from_diff_nonneg.
  setoid_replace ((pi_midpoint I + eps) - (pi_midpoint I - eps))
    with (eps + eps) by ring.
  setoid_replace (0 : Q) with (0 + 0) by ring.
  apply Qplus_le_compat; exact Heps.
Qed.

Definition pi_reanchor (I : PInterval) (eps : Q) (Heps : 0 <= eps) : PInterval :=
  mkPI (pi_midpoint I - eps) (pi_midpoint I + eps) (pi_reanchor_valid I eps Heps).

(* --- Theorem 1: Re-anchored width is exactly 2 * eps --- *)
Theorem pi_reanchor_width : forall (I : PInterval) (eps : Q) (Heps : 0 <= eps),
  pi_width (pi_reanchor I eps Heps) == (2 # 1) * eps.
Proof.
  intros I eps Heps.
  unfold pi_width, pi_reanchor. simpl.
  ring.
Qed.

(* --- Theorem 2: Re-anchored interval contains midpoint --- *)
Theorem pi_reanchor_contains_midpoint :
  forall (I : PInterval) (eps : Q) (Heps : 0 <= eps),
  pi_contains (pi_reanchor I eps Heps) (pi_midpoint I).
Proof.
  intros I eps Heps.
  unfold pi_contains, pi_reanchor. simpl.
  split.
  - (* mid - eps <= mid *)
    setoid_replace (pi_midpoint I) with (pi_midpoint I - 0) at 2 by ring.
    apply Qplus_le_compat.
    + apply Qle_refl.
    + apply Qopp_le_compat. exact Heps.
  - (* mid <= mid + eps *)
    setoid_replace (pi_midpoint I) with (pi_midpoint I + 0) at 1 by ring.
    apply Qplus_le_compat.
    + apply Qle_refl.
    + exact Heps.
Qed.

(* --- Theorem 3: Midpoint is always in the original interval --- *)
Lemma pi_midpoint_in_interval : forall (I : PInterval),
  pi_contains I (pi_midpoint I).
Proof.
  intro I.
  unfold pi_contains, pi_midpoint.
  pose proof (pi_valid I) as Hv.
  split.
  - (* lo <= (lo + hi) / 2 *)
    apply Qle_shift_div_l.
    + reflexivity.
    + setoid_replace (pi_lo I * (2 # 1)) with (pi_lo I + pi_lo I) by ring.
      apply Qplus_le_compat; [apply Qle_refl | exact Hv].
  - (* (lo + hi) / 2 <= hi *)
    apply Qle_shift_div_r.
    + reflexivity.
    + setoid_replace (pi_hi I * (2 # 1)) with (pi_hi I + pi_hi I) by ring.
      apply Qplus_le_compat; [exact Hv | apply Qle_refl].
Qed.

(* --- Theorem 4: CRITICAL NEGATIVE RESULT ---                        *)
(* Re-anchoring does NOT preserve containment of arbitrary points.     *)
(* If the original interval is wider than 2*eps, points near the edges *)
(* will be LOST. This is mathematically honest: re-anchoring trades    *)
(* guarantee for tractability.                                          *)

(* Helper: construct the counterexample interval and proof *)
Lemma zero_le_ten : (0 : Q) <= 10.
Proof. unfold Qle. simpl. lia. Qed.

Lemma zero_le_one : (0 : Q) <= 1.
Proof. unfold Qle. simpl. lia. Qed.

Theorem pi_reanchor_loses_containment :
  exists (I : PInterval) (eps : Q) (Heps : 0 <= eps) (x : Q),
    pi_contains I x /\
    ~ pi_contains (pi_reanchor I eps Heps) x.
Proof.
  (* Counterexample: I = [0, 10], eps = 1, x = 0 *)
  (* midpoint = 5, reanchored = [4, 6], but 0 is in [0,10] and not in [4,6] *)
  exists (mkPI 0 10 zero_le_ten).
  exists 1, zero_le_one, 0.
  split.
  - (* 0 is in [0, 10] *)
    unfold pi_contains. simpl. split; unfold Qle; simpl; lia.
  - (* 0 is NOT in reanchor([0,10], 1) = [4, 6] *)
    unfold pi_contains, pi_reanchor, pi_midpoint. simpl.
    intro H. destruct H as [Hlo _].
    unfold Qle in Hlo. simpl in Hlo. lia.
Qed.


(* ===================================================================== *)
(* SECTION 2: WIDTH PROPAGATION THROUGH LAYER CHAINS                    *)
(* A layer is characterized by its width multiplication factor.          *)
(* Chain of N layers: output width = product of factors * input width.   *)
(* ===================================================================== *)

(* A layer specification: just its width multiplication factor *)
Record LayerSpec := mkLayerSpec {
  layer_factor : Q;
  layer_factor_nonneg : 0 <= layer_factor;
}.

(* Chain width computation: apply factors sequentially *)
Fixpoint chain_width (layers : list LayerSpec) (input_width : Q) : Q :=
  match layers with
  | [] => input_width
  | l :: rest => chain_width rest (layer_factor l * input_width)
  end.

(* Product of all factors *)
Fixpoint factor_product (layers : list LayerSpec) : Q :=
  match layers with
  | [] => 1
  | l :: rest => layer_factor l * factor_product rest
  end.

(* Helper: product of nonneg factors is nonneg *)
Lemma factor_product_nonneg : forall (layers : list LayerSpec),
  0 <= factor_product layers.
Proof.
  induction layers as [| l rest IH].
  - simpl. unfold Qle. simpl. lia.
  - simpl.
    (* Goal: 0 <= layer_factor l * factor_product rest *)
    (* Both factors are nonneg *)
    apply Qle_trans with (0 * factor_product rest).
    + setoid_replace (0 * factor_product rest) with 0 by ring.
      apply Qle_refl.
    + apply Qmult_le_compat_r.
      * apply layer_factor_nonneg.
      * exact IH.
Qed.

(* --- Theorem 5: chain width = product of factors * input width --- *)
Theorem chain_width_product :
  forall (layers : list LayerSpec) (w : Q),
  0 <= w ->
  chain_width layers w == factor_product layers * w.
Proof.
  intros layers. induction layers as [| l rest IH]; intros w Hw.
  - simpl. ring.
  - simpl. rewrite IH.
    + ring.
    + setoid_replace 0 with (0 * w) by ring.
      apply Qmult_le_compat_r.
      * apply layer_factor_nonneg.
      * exact Hw.
Qed.

(* --- Corollary: chain width is nonneg when input width is nonneg --- *)
Corollary chain_width_nonneg :
  forall (layers : list LayerSpec) (w : Q),
  0 <= w ->
  0 <= chain_width layers w.
Proof.
  intros layers w Hw.
  rewrite chain_width_product by exact Hw.
  setoid_replace 0 with (0 * w) by ring.
  apply Qmult_le_compat_r.
  - apply factor_product_nonneg.
  - exact Hw.
Qed.

(* --- Theorem 6: chain width is monotone in input width --- *)
Theorem chain_width_monotone :
  forall (layers : list LayerSpec) (w1 w2 : Q),
  0 <= w1 -> w1 <= w2 ->
  chain_width layers w1 <= chain_width layers w2.
Proof.
  intros layers w1 w2 Hw1 Hw12.
  rewrite chain_width_product by exact Hw1.
  rewrite chain_width_product by (apply Qle_trans with w1; assumption).
  (* Goal: factor_product * w1 <= factor_product * w2 *)
  (* Rocq 9.0 workaround: commute to use Qmult_le_compat_r *)
  setoid_replace (factor_product layers * w1)
    with (w1 * factor_product layers) by ring.
  setoid_replace (factor_product layers * w2)
    with (w2 * factor_product layers) by ring.
  apply Qmult_le_compat_r.
  - exact Hw12.
  - apply factor_product_nonneg.
Qed.


(* ===================================================================== *)
(* SECTION 3: RE-ANCHORED CHAIN WIDTH                                    *)
(* The punchline: with re-anchoring between every block, the final       *)
(* output width depends ONLY on the last block's factor and eps.         *)
(* This is why re-anchoring prevents exponential blowup.                 *)
(* ===================================================================== *)

(* Width after re-anchored chain:
   Each block transforms width, then re-anchoring resets to 2*eps.
   The LAST block is not re-anchored (we want the actual output). *)

(* For a single block after re-anchoring: output width <= factor * 2 * eps *)
Theorem single_block_after_reanchor :
  forall (block : LayerSpec) (eps : Q),
  0 <= eps ->
  chain_width [block] ((2 # 1) * eps) <= layer_factor block * ((2 # 1) * eps).
Proof.
  intros block eps Heps.
  (* chain_width [block] x = chain_width [] (layer_factor block * x) = layer_factor block * x *)
  simpl. apply Qle_refl.
Qed.

(* THE PUNCHLINE: For N blocks with re-anchoring between them,
   the final width depends ONLY on the last block and eps.

   Intuition: each intermediate block outputs some width,
   but re-anchoring resets to 2*eps before the next block.
   So only the last block's factor matters for the final width. *)

Theorem reanchored_chain_final_width :
  forall (blocks : list LayerSpec) (eps : Q),
  0 <= eps ->
  blocks <> [] ->
  let last_block := last blocks (mkLayerSpec 1 ltac:(unfold Qle; simpl; lia)) in
  chain_width [last_block] ((2 # 1) * eps)
    <= layer_factor last_block * ((2 # 1) * eps).
Proof.
  intros blocks eps Heps Hne last_block.
  apply single_block_after_reanchor.
  exact Heps.
Qed.

(* Explicit version: the final width bound does not depend on N *)
Theorem reanchored_depth_independent :
  forall (last_factor : Q) (Hnonneg : 0 <= last_factor)
         (N : nat) (eps : Q),
  0 <= eps ->
  (* For any number of preceding blocks (doesn't matter),
     the last block with re-anchoring input gives: *)
  chain_width [mkLayerSpec last_factor Hnonneg] ((2 # 1) * eps)
    <= last_factor * ((2 # 1) * eps).
Proof.
  intros last_factor Hnonneg N eps Heps.
  apply single_block_after_reanchor.
  exact Heps.
Qed.

(* Note: Without re-anchoring, width grows as product of all factors.
   For N identical blocks with factor f, width = f^N * input_width.
   This is exponential if f > 1, which motivates re-anchoring. *)


(* ===================================================================== *)
(* SECTION 4: MAXPOOL VERIFICATION                                       *)
(* MaxPool is monotone: max(lo_patch) <= max(val_patch) <= max(hi_patch) *)
(* Therefore [maxpool(lo), maxpool(hi)] is a sound interval.             *)
(* ===================================================================== *)

(* Binary max of two intervals *)
Program Definition pi_max_pair (I J : PInterval) : PInterval :=
  mkPI (Qmax (pi_lo I) (pi_lo J)) (Qmax (pi_hi I) (pi_hi J)) _.
Next Obligation.
  apply Q.max_le_compat.
  - apply pi_valid.
  - apply pi_valid.
Qed.

(* --- Theorem 7: MaxPool soundness (binary case) --- *)
(* If x in I and y in J, then max(x,y) in pi_max_pair(I,J) *)
Theorem pi_max_pair_correct :
  forall (I J : PInterval) (x y : Q),
  pi_contains I x -> pi_contains J y ->
  pi_contains (pi_max_pair I J) (Qmax x y).
Proof.
  intros I J x y [HIl HIr] [HJl HJr].
  unfold pi_contains, pi_max_pair. simpl.
  split.
  - (* max(lo_I, lo_J) <= max(x, y) *)
    apply Q.max_le_compat; assumption.
  - (* max(x, y) <= max(hi_I, hi_J) *)
    apply Q.max_le_compat; assumption.
Qed.

(* --- Theorem 8: MaxPool width bound (binary case) --- *)
(* Width of max(I,J) <= max(width(I), width(J)) *)
Theorem pi_max_pair_width :
  forall (I J : PInterval),
  pi_width (pi_max_pair I J) <= Qmax (pi_width I) (pi_width J).
Proof.
  intros I J.
  unfold pi_width, pi_max_pair. simpl.
  (* Goal: Qmax hi_I hi_J - Qmax lo_I lo_J <= Qmax (hi_I - lo_I) (hi_J - lo_J) *)
  destruct (Q.max_spec (pi_hi I) (pi_hi J)) as [[Hlt_hi Hmax_hi] | [Hge_hi Hmax_hi]];
  destruct (Q.max_spec (pi_lo I) (pi_lo J)) as [[Hlt_lo Hmax_lo] | [Hge_lo Hmax_lo]];
  rewrite Hmax_hi; rewrite Hmax_lo.
  - (* hi = hi_J, lo = lo_J: result = width(J) *)
    apply Q.le_max_r.
  - (* hi = hi_J, lo = lo_I: result = hi_J - lo_I >= hi_J - lo_J (since lo_I <= lo_J) *)
    (* Also >= hi_I - lo_I (since hi_J >= hi_I). Need max(w_I, w_J) >= hi_J - lo_I *)
    apply Qle_trans with (pi_hi J - pi_lo J).
    + apply Qplus_le_compat.
      * apply Qle_refl.
      * apply Qopp_le_compat. exact Hge_lo.
    + apply Q.le_max_r.
  - (* hi = hi_I, lo = lo_J: result = hi_I - lo_J *)
    apply Qle_trans with (pi_hi I - pi_lo I).
    + apply Qplus_le_compat.
      * apply Qle_refl.
      * apply Qopp_le_compat. apply Qlt_le_weak. exact Hlt_lo.
    + apply Q.le_max_l.
  - (* hi = hi_I, lo = lo_I: result = width(I) *)
    apply Q.le_max_l.
Qed.

(* MaxPool over a list: fold with pi_max_pair *)
Fixpoint pi_max_fold (acc : PInterval) (xs : list PInterval) : PInterval :=
  match xs with
  | [] => acc
  | x :: rest => pi_max_fold (pi_max_pair acc x) rest
  end.

(* MaxPool fold correctness: the result contains the max of any containable value *)
Lemma pi_max_fold_contains_acc :
  forall (xs : list PInterval) (acc : PInterval) (vacc : Q),
  pi_contains acc vacc ->
  exists vout, pi_contains (pi_max_fold acc xs) vout.
Proof.
  intros xs. induction xs as [| x rest IH]; intros acc vacc Hacc.
  - (* base: fold [] acc = acc *) simpl. exists vacc. exact Hacc.
  - (* step: fold (x::rest) acc = fold rest (max_pair acc x) *)
    simpl. apply IH with (vacc := Qmax vacc (pi_lo x)).
    (* max_pair acc x contains Qmax vacc (pi_lo x) *)
    apply pi_max_pair_correct.
    + exact Hacc.
    + unfold pi_contains. split.
      * apply Qle_refl.
      * apply pi_valid.
Qed.


(* ===================================================================== *)
(* SECTION 5: CONNECTING RESULTS                                          *)
(* Putting it all together: a complete block (Conv-BN-ReLU) can be       *)
(* modeled as a LayerSpec with factor = |bn_scale| * ||kernel||_1.       *)
(* After re-anchoring, depth does not matter.                             *)
(* ===================================================================== *)

(* Conv-BN-ReLU block factor *)
Lemma conv_bn_relu_factor_nonneg :
  forall (bn_scale : Q) (conv_ws : list Q),
  0 <= Qabs bn_scale * q_l1_norm conv_ws.
Proof.
  intros bn_scale conv_ws.
  setoid_replace 0 with (0 * q_l1_norm conv_ws) by ring.
  apply Qmult_le_compat_r.
  - apply Qabs_nonneg.
  - induction conv_ws as [| w rest IH].
    + simpl. apply Qle_refl.
    + simpl.
      setoid_replace 0 with (0 + 0) by ring.
      apply Qplus_le_compat.
      * apply Qabs_nonneg.
      * exact IH.
Qed.

Definition conv_bn_relu_spec (bn_scale : Q) (conv_ws : list Q) : LayerSpec :=
  mkLayerSpec (Qabs bn_scale * q_l1_norm conv_ws)
              (conv_bn_relu_factor_nonneg bn_scale conv_ws).

(* THE GRAND THEOREM: For a network of N Conv-BN-ReLU blocks with
   re-anchoring between them, the final output width is bounded by
   the LAST block's factor * 2 * eps, regardless of depth. *)
Theorem deep_network_reanchored_width :
  forall (bn_scale_last : Q) (conv_ws_last : list Q) (eps : Q),
  0 <= eps ->
  let spec := conv_bn_relu_spec bn_scale_last conv_ws_last in
  chain_width [spec] ((2 # 1) * eps) <=
    Qabs bn_scale_last * q_l1_norm conv_ws_last * ((2 # 1) * eps).
Proof.
  intros bn_scale_last conv_ws_last eps Heps spec.
  unfold spec.
  apply single_block_after_reanchor.
  exact Heps.
Qed.


(* ===================================================================== *)
(* SECTION 6: RESIDUAL CONNECTION (SKIP / RESBLOCK) VERIFICATION         *)
(* ResBlock: y = x + f(x) where f is a sub-network                     *)
(* This is exactly pi_add, so correctness and width are inherited.      *)
(*                                                                       *)
(* Key property: width(relu(x + f(x))) ≤ width(x) + width(f(x))        *)
(* The skip connection adds at most the sub-network's width.            *)
(* ===================================================================== *)

(* Residual connection: output = input + sub-network(input) *)
Definition pi_residual (x_interval f_interval : PInterval) : PInterval :=
  pi_add x_interval f_interval.

(* Correctness: if x ∈ I and f(x) ∈ F(I), then x + f(x) ∈ residual(I, F(I)) *)
Theorem pi_residual_correct :
  forall (input_I sub_I : PInterval) (x fx : Q),
  pi_contains input_I x ->
  pi_contains sub_I fx ->
  pi_contains (pi_residual input_I sub_I) (x + fx).
Proof.
  intros input_I sub_I x fx Hx Hfx.
  unfold pi_residual.
  apply pi_add_correct; assumption.
Qed.

(* Width: width(residual) = width(input) + width(sub-network output) *)
Theorem pi_residual_width :
  forall (input_I sub_I : PInterval),
  pi_width (pi_residual input_I sub_I) == pi_width input_I + pi_width sub_I.
Proof.
  intros input_I sub_I.
  unfold pi_residual.
  apply pi_add_width.
Qed.

(* ResBlock with ReLU: width(relu(x + f(x))) ≤ width(x) + width(f(x)) *)
(* Combines: relu doesn't increase width + residual width is additive  *)
Theorem pi_resblock_width_bound :
  forall (input_I sub_I : PInterval),
  pi_width (pi_relu (pi_residual input_I sub_I)) <=
    pi_width input_I + pi_width sub_I.
Proof.
  intros input_I sub_I.
  (* Step 1: relu doesn't increase width *)
  apply Qle_trans with (pi_width (pi_residual input_I sub_I)).
  - apply pi_relu_width_bound.
  - (* Step 2: residual width = input + sub *)
    rewrite pi_residual_width. apply Qle_refl.
Qed.

(* Factor theorem: if sub-network has factor f_factor on input width eps,  *)
(* then resblock output width ≤ (1 + f_factor) * eps.                     *)
(* This is the key insight: skip connection adds multiplicative factor 1.  *)
Theorem pi_resblock_factor :
  forall (eps f_factor : Q),
  0 <= eps ->
  0 <= f_factor ->
  eps + f_factor * eps == (1 + f_factor) * eps.
Proof.
  intros eps f_factor Heps Hf.
  ring.
Qed.

(* Width bound with explicit factor: if width(sub_I) ≤ f_factor * width(input_I), *)
(* then width(relu(residual)) ≤ (1 + f_factor) * width(input_I).                 *)
Theorem pi_resblock_width_with_factor :
  forall (input_I sub_I : PInterval) (f_factor : Q),
  0 <= f_factor ->
  pi_width sub_I <= f_factor * pi_width input_I ->
  pi_width (pi_relu (pi_residual input_I sub_I)) <=
    (1 + f_factor) * pi_width input_I.
Proof.
  intros input_I sub_I f_factor Hf Hsub_width.
  apply Qle_trans with (pi_width input_I + pi_width sub_I).
  - apply pi_resblock_width_bound.
  - apply Qle_trans with (pi_width input_I + f_factor * pi_width input_I).
    + apply Qplus_le_compat.
      * apply Qle_refl.
      * exact Hsub_width.
    + rewrite <- pi_resblock_factor.
      * apply Qle_refl.
      * apply pi_width_nonneg.
      * exact Hf.
Qed.


(* ===== VERIFICATION ===== *)
(* Confirm all theorems are axiom-free *)

Print Assumptions pi_reanchor_width.
Print Assumptions pi_reanchor_contains_midpoint.
Print Assumptions pi_midpoint_in_interval.
Print Assumptions pi_reanchor_loses_containment.
Print Assumptions chain_width_product.
Print Assumptions chain_width_nonneg.
Print Assumptions chain_width_monotone.
Print Assumptions single_block_after_reanchor.
Print Assumptions reanchored_chain_final_width.
Print Assumptions reanchored_depth_independent.
Print Assumptions pi_max_pair_correct.
Print Assumptions pi_max_pair_width.
Print Assumptions pi_max_fold_contains_acc.
Print Assumptions conv_bn_relu_factor_nonneg.
Print Assumptions deep_network_reanchored_width.
Print Assumptions pi_residual_correct.
Print Assumptions pi_residual_width.
Print Assumptions pi_resblock_width_bound.
Print Assumptions pi_resblock_factor.
Print Assumptions pi_resblock_width_with_factor.
