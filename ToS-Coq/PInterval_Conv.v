(* ========================================================================= *)
(*  CONV2D & BATCHNORM VERIFICATION                                        *)
(*  Part of: Regulus -- Verified AI Computation                             *)
(*                                                                          *)
(*  Author:  Horsocrates | Date: February 2026                              *)
(*                                                                          *)
(*  E/R/R INTERPRETATION:                                                   *)
(*    Elements = PIntervals (neuron activations as intervals)               *)
(*    Roles    = pi_affine (BN), pi_conv_pixel (Conv2d), composition        *)
(*    Rules    = width propagation: verified bounds on output uncertainty    *)
(*                                                                          *)
(*  P4 PHILOSOPHY:                                                          *)
(*    Conv2d = structured dot product over spatial patches.                  *)
(*    BatchNorm = affine re-scaling (the network's own re-anchoring).       *)
(*    The interval at each layer IS the knowledge at that step --           *)
(*    not an approximation, but the honest extent of determination.         *)
(*                                                                          *)
(*  KEY THEOREMS:                                                           *)
(*    1. pi_affine_width: width(BN(x)) = |scale| * width(x)               *)
(*    2. pi_conv_pixel_width: width(conv) = weighted_width_sum             *)
(*    3. pi_conv_bn_relu_width_bound:                                       *)
(*         width(ReLU(BN(Conv(x)))) <= |bn_scale| * eps * ||kernel||_1      *)
(*                                                                          *)
(*  AXIOMS: NONE. Fully constructive. Extraction-compatible.                *)
(*                                                                          *)
(* ========================================================================= *)

From ToS Require Import PInterval.
From ToS Require Import PInterval_Linear.

Require Import Coq.QArith.QArith.
Require Import Coq.QArith.Qabs.
Require Import Coq.QArith.Qminmax.
Require Import Coq.micromega.Lia.
Require Import Coq.ZArith.ZArith.
Require Import Coq.Setoids.Setoid.
Require Import Coq.Lists.List.
Import ListNotations.

Open Scope Q_scope.


(* ===== SECTION 1: pi_point_width ===== *)
(* Width of a point interval is 0.       *)

Lemma pi_point_width : forall b : Q, pi_width (pi_point b) == 0.
Proof.
  intro b. unfold pi_width, pi_point. simpl. ring.
Qed.

(* Containment in a point interval *)
Lemma pi_point_contains : forall b : Q, pi_contains (pi_point b) b.
Proof.
  intro b. unfold pi_contains, pi_point. simpl. split; apply Qle_refl.
Qed.


(* ===== SECTION 2: pi_affine -- BatchNorm (single channel) ===== *)
(* BN in eval mode: y = scale * x + shift                         *)
(* This is pi_scale followed by addition of a point interval.     *)
(*                                                                  *)
(* Python equivalent (layers.py:171-172):                          *)
(*   new_lo = scale_pos * x.lo + scale_neg * x.hi + shift         *)
(*   new_hi = scale_pos * x.hi + scale_neg * x.lo + shift         *)
(* pi_scale handles pos/neg via Qmin/Qmax uniformly.               *)

Definition pi_affine (w : Q) (x : PInterval) (b : Q) : PInterval :=
  pi_add (pi_scale w x) (pi_point b).

Theorem pi_affine_correct : forall (w : Q) (x : PInterval) (b : Q) (v : Q),
  pi_contains x v -> pi_contains (pi_affine w x b) (w * v + b).
Proof.
  intros w x b v Hv.
  unfold pi_affine.
  apply pi_add_correct.
  - apply pi_scale_correct. exact Hv.
  - apply pi_point_contains.
Qed.

Theorem pi_affine_width : forall (w : Q) (x : PInterval) (b : Q),
  pi_width (pi_affine w x b) == Qabs w * pi_width x.
Proof.
  intros w x b.
  unfold pi_affine.
  rewrite pi_add_width.
  rewrite pi_scale_width.
  rewrite pi_point_width.
  ring.
Qed.

(* Corollary: affine does not increase width when |scale| <= 1 *)
Corollary pi_affine_width_bound : forall (w : Q) (x : PInterval) (b : Q),
  Qabs w <= 1 -> pi_width (pi_affine w x b) <= pi_width x.
Proof.
  intros w x b Hw.
  rewrite pi_affine_width.
  setoid_replace (pi_width x) with (1 * pi_width x) at 2 by ring.
  apply Qmult_le_compat_r.
  - exact Hw.
  - apply pi_width_nonneg.
Qed.


(* ===== SECTION 3: pi_channelwise_affine -- Multi-channel BatchNorm ===== *)
(* BN applies an independent affine transform per channel.                  *)
(* ws = list of per-channel scales, bs = list of per-channel shifts.       *)

Fixpoint pi_channelwise_affine (ws bs : list Q) (xs : list PInterval)
    : list PInterval :=
  match ws, bs, xs with
  | w :: ws', b :: bs', x :: xs' =>
      pi_affine w x b :: pi_channelwise_affine ws' bs' xs'
  | _, _, _ => []
  end.

(* Length preservation *)
Lemma pi_channelwise_affine_length :
  forall (ws bs : list Q) (xs : list PInterval),
  length ws = length xs ->
  length bs = length xs ->
  length (pi_channelwise_affine ws bs xs) = length xs.
Proof.
  intro ws. induction ws as [| w ws' IH]; intros bs xs Hlen1 Hlen2.
  - simpl in Hlen1. symmetry in Hlen1. apply length_zero_iff_nil in Hlen1.
    subst. simpl. reflexivity.
  - destruct xs as [| x xs']; [simpl in Hlen1; discriminate |].
    destruct bs as [| b bs']; [simpl in Hlen2; discriminate |].
    simpl. f_equal. apply IH; simpl in *; lia.
Qed.

(* Pointwise correctness via Forall2 *)
(* Helper: apply function element-wise to two lists *)
Fixpoint zipWith_affine (ws bs vs : list Q) : list Q :=
  match ws, bs, vs with
  | w :: ws', b :: bs', v :: vs' =>
      (w * v + b) :: zipWith_affine ws' bs' vs'
  | _, _, _ => []
  end.

Theorem pi_channelwise_affine_correct :
  forall (ws bs : list Q) (xs : list PInterval) (vs : list Q),
  length ws = length xs ->
  length bs = length xs ->
  length xs = length vs ->
  Forall2 pi_contains xs vs ->
  Forall2 pi_contains
    (pi_channelwise_affine ws bs xs)
    (zipWith_affine ws bs vs).
Proof.
  intro ws. induction ws as [| w ws' IH];
  intros bs xs vs Hlen1 Hlen2 Hlen3 HF.
  - simpl. constructor.
  - destruct xs as [| x xs']; [simpl in Hlen1; discriminate |].
    destruct bs as [| b bs']; [simpl in Hlen2; discriminate |].
    destruct vs as [| v vs']; [simpl in Hlen3; discriminate |].
    inversion HF. subst.
    simpl. constructor.
    + apply pi_affine_correct. assumption.
    + apply IH; simpl in *; try lia. assumption.
Qed.

(* Per-channel width: each output_i has width = |w_i| * width(x_i) *)
(* We prove this via Forall2 on widths *)
Lemma pi_channelwise_affine_widths :
  forall (ws bs : list Q) (xs : list PInterval),
  length ws = length xs ->
  length bs = length xs ->
  forall i, (i < length xs)%nat ->
  pi_width (nth i (pi_channelwise_affine ws bs xs) (pi_point 0))
    == Qabs (nth i ws 0) * pi_width (nth i xs (pi_point 0)).
Proof.
  intro ws. induction ws as [| w ws' IH];
  intros bs xs Hlen1 Hlen2 i Hi.
  - simpl in Hlen1. symmetry in Hlen1. apply length_zero_iff_nil in Hlen1.
    subst. simpl in Hi. lia.
  - destruct xs as [| x xs']; [simpl in Hlen1; discriminate |].
    destruct bs as [| b bs']; [simpl in Hlen2; discriminate |].
    destruct i as [| i'].
    + simpl. apply pi_affine_width.
    + simpl. apply IH; simpl in *; lia.
Qed.


(* ===== SECTION 4: pi_conv_pixel -- Single Conv2d output pixel ===== *)
(* Each output pixel of Conv2d = weighted dot product of kernel with  *)
(* an input patch, plus a bias. Kernel weights are EXACT (scalars),  *)
(* input patch elements are INTERVALS.                                *)
(*                                                                     *)
(* Python equivalent (layers.py:220-223):                             *)
(*   out_lo = conv(lo, W_pos) + conv(hi, W_neg) + bias               *)
(*   out_hi = conv(hi, W_pos) + conv(lo, W_neg) + bias               *)
(* For a single pixel, this is exactly pi_wdot + bias.                *)

Definition pi_conv_pixel (ws : list Q) (patch : list PInterval) (b : Q)
    : PInterval :=
  pi_add (pi_wdot ws patch) (pi_point b).

Theorem pi_conv_pixel_correct :
  forall (ws : list Q) (patch : list PInterval) (vs : list Q) (b : Q),
  length ws = length patch ->
  length patch = length vs ->
  Forall2 pi_contains patch vs ->
  pi_contains (pi_conv_pixel ws patch b) (qdot ws vs + b).
Proof.
  intros ws patch vs b Hlen1 Hlen2 HF.
  unfold pi_conv_pixel.
  apply pi_add_correct.
  - apply pi_wdot_correct; assumption.
  - apply pi_point_contains.
Qed.

(* Exact width: bias adds zero width *)
Theorem pi_conv_pixel_width :
  forall (ws : list Q) (patch : list PInterval) (b : Q),
  length ws = length patch ->
  pi_width (pi_conv_pixel ws patch b) == weighted_width_sum ws patch.
Proof.
  intros ws patch b Hlen.
  unfold pi_conv_pixel.
  rewrite pi_add_width.
  rewrite pi_wdot_width by exact Hlen.
  rewrite pi_point_width.
  ring.
Qed.

(* Uniform width bound: if all input widths <= eps *)
Theorem pi_conv_pixel_width_uniform_bound :
  forall (ws : list Q) (patch : list PInterval) (b : Q) (eps : Q),
  length ws = length patch ->
  (forall x, In x patch -> pi_width x <= eps) ->
  0 <= eps ->
  pi_width (pi_conv_pixel ws patch b) <= eps * q_l1_norm ws.
Proof.
  intros ws patch b eps Hlen Hwidth Heps.
  unfold pi_conv_pixel.
  rewrite pi_add_width.
  rewrite pi_point_width.
  setoid_replace (pi_width (pi_wdot ws patch) + 0)
    with (pi_width (pi_wdot ws patch)) by ring.
  apply pi_wdot_width_uniform_bound; assumption.
Qed.


(* ===== SECTION 5: pi_conv_channel -- Full spatial output ===== *)
(* One output channel = same kernel applied to all spatial patches, *)
(* each producing one output pixel.                                 *)

Fixpoint pi_conv_channel
  (ws : list Q) (patches : list (list PInterval)) (b : Q)
    : list PInterval :=
  match patches with
  | [] => []
  | patch :: rest => pi_conv_pixel ws patch b :: pi_conv_channel ws rest b
  end.

(* Length of output = number of patches *)
Lemma pi_conv_channel_length :
  forall (ws : list Q) (patches : list (list PInterval)) (b : Q),
  length (pi_conv_channel ws patches b) = length patches.
Proof.
  intros ws patches. induction patches as [| patch rest IH]; intro b.
  - simpl. reflexivity.
  - simpl. f_equal. apply IH.
Qed.

(* Width bound: every output pixel has width <= eps * l1_norm(ws) *)
Theorem pi_conv_channel_width_bound :
  forall (ws : list Q) (patches : list (list PInterval)) (b : Q) (eps : Q),
  (forall patch, In patch patches ->
     length ws = length patch /\
     (forall x, In x patch -> pi_width x <= eps)) ->
  0 <= eps ->
  forall out, In out (pi_conv_channel ws patches b) ->
    pi_width out <= eps * q_l1_norm ws.
Proof.
  intros ws patches b eps Hpatches Heps.
  induction patches as [| patch rest IH].
  - simpl. intros out Hin. destruct Hin.
  - intros out Hin.
    simpl in Hin. destruct Hin as [Heq | Hin_rest].
    + subst out.
      assert (Hpatch : length ws = length patch /\
              (forall x, In x patch -> pi_width x <= eps)).
      { apply Hpatches. left. reflexivity. }
      destruct Hpatch as [Hlen Hwidth].
      apply pi_conv_pixel_width_uniform_bound; assumption.
    + apply IH.
      * intros p Hp. apply Hpatches. right. exact Hp.
      * exact Hin_rest.
Qed.

(* Correctness: all output pixels contain the true convolution values *)
Fixpoint map_qdot_bias (ws : list Q) (vals_list : list (list Q)) (b : Q)
    : list Q :=
  match vals_list with
  | [] => []
  | vs :: rest => (qdot ws vs + b) :: map_qdot_bias ws rest b
  end.

Theorem pi_conv_channel_correct :
  forall (ws : list Q) (patches : list (list PInterval))
         (vals_list : list (list Q)) (b : Q),
  length patches = length vals_list ->
  (forall i, (i < length patches)%nat ->
     length ws = length (nth i patches []) /\
     length (nth i patches []) = length (nth i vals_list []) /\
     Forall2 pi_contains (nth i patches []) (nth i vals_list [])) ->
  Forall2 pi_contains
    (pi_conv_channel ws patches b)
    (map_qdot_bias ws vals_list b).
Proof.
  intros ws patches vals_list b Hlen Hspec.
  generalize dependent vals_list.
  induction patches as [| patch rest IH]; intros vals_list Hlen Hspec.
  - destruct vals_list; [constructor | simpl in Hlen; discriminate].
  - destruct vals_list as [| vs vrest]; [simpl in Hlen; discriminate |].
    simpl. constructor.
    + assert (H0 := Hspec 0%nat ltac:(simpl; lia)).
      simpl in H0. destruct H0 as [Hlen1 [Hlen2 HF]].
      apply pi_conv_pixel_correct; assumption.
    + apply IH.
      * simpl in Hlen. lia.
      * intros i Hi. assert (H := Hspec (S i) ltac:(simpl; lia)).
        simpl in H. exact H.
Qed.


(* ===== SECTION 6: THE PUNCHLINE -- Conv -> BN -> ReLU ===== *)
(*                                                              *)
(* The full Conv-BN-ReLU block width bound.                     *)
(* This is the compositional verification that a standard CNN   *)
(* block has bounded uncertainty propagation.                    *)
(*                                                              *)
(* width(ReLU(BN(Conv(x)))) <= |bn_scale| * eps * ||kernel||_1 *)

Theorem pi_conv_bn_relu_width_bound :
  forall (conv_ws : list Q) (patch : list PInterval)
         (conv_bias : Q) (bn_scale : Q) (bn_shift : Q) (eps : Q),
  length conv_ws = length patch ->
  (forall x, In x patch -> pi_width x <= eps) ->
  0 <= eps ->
  pi_width
    (pi_relu
      (pi_affine bn_scale
        (pi_conv_pixel conv_ws patch conv_bias) bn_shift))
    <= Qabs bn_scale * (eps * q_l1_norm conv_ws).
Proof.
  intros conv_ws patch conv_bias bn_scale bn_shift eps
         Hlen Hwidth Heps.
  (* Step 1: ReLU does not increase width *)
  apply Qle_trans with
    (pi_width (pi_affine bn_scale
                (pi_conv_pixel conv_ws patch conv_bias) bn_shift)).
  { apply pi_relu_width_bound. }
  (* Step 2: BN width = |bn_scale| * conv_width *)
  rewrite pi_affine_width.
  (* Step 3: conv_width <= eps * l1_norm *)
  (* Goal: |bn_scale| * width(conv_pixel) <= |bn_scale| * (eps * l1_norm) *)
  assert (Hconv : pi_width (pi_conv_pixel conv_ws patch conv_bias)
                  <= eps * q_l1_norm conv_ws).
  { apply pi_conv_pixel_width_uniform_bound; assumption. }
  setoid_replace (Qabs bn_scale * (eps * q_l1_norm conv_ws))
    with ((eps * q_l1_norm conv_ws) * Qabs bn_scale) by ring.
  setoid_replace (Qabs bn_scale * pi_width (pi_conv_pixel conv_ws patch conv_bias))
    with (pi_width (pi_conv_pixel conv_ws patch conv_bias) * Qabs bn_scale) by ring.
  apply Qmult_le_compat_r.
  - exact Hconv.
  - apply Qabs_nonneg.
Qed.

(* Alternative form with explicit multiplication *)
Corollary pi_conv_bn_relu_width_bound_alt :
  forall (conv_ws : list Q) (patch : list PInterval)
         (conv_bias : Q) (bn_scale : Q) (bn_shift : Q) (eps : Q),
  length conv_ws = length patch ->
  (forall x, In x patch -> pi_width x <= eps) ->
  0 <= eps ->
  pi_width
    (pi_relu
      (pi_affine bn_scale
        (pi_conv_pixel conv_ws patch conv_bias) bn_shift))
    <= Qabs bn_scale * eps * q_l1_norm conv_ws.
Proof.
  intros.
  apply Qle_trans with (Qabs bn_scale * (eps * q_l1_norm conv_ws)).
  - apply pi_conv_bn_relu_width_bound; assumption.
  - setoid_replace (Qabs bn_scale * eps * q_l1_norm conv_ws)
      with (Qabs bn_scale * (eps * q_l1_norm conv_ws)) by ring.
    apply Qle_refl.
Qed.


(* ===== VERIFICATION ===== *)
(* Confirm all theorems are axiom-free *)

Print Assumptions pi_point_width.
Print Assumptions pi_affine_correct.
Print Assumptions pi_affine_width.
Print Assumptions pi_affine_width_bound.
Print Assumptions pi_channelwise_affine_correct.
Print Assumptions pi_channelwise_affine_widths.
Print Assumptions pi_conv_pixel_correct.
Print Assumptions pi_conv_pixel_width.
Print Assumptions pi_conv_pixel_width_uniform_bound.
Print Assumptions pi_conv_channel_width_bound.
Print Assumptions pi_conv_channel_correct.
Print Assumptions pi_conv_bn_relu_width_bound.
Print Assumptions pi_conv_bn_relu_width_bound_alt.
