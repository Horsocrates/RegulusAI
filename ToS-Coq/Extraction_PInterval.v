(* ========================================================================= *)
(*  Extraction: PInterval + Linear + Conv + Composition -> OCaml            *)
(*  Part of: Regulus Phase 1 - Verified AI Computation                      *)
(*                                                                          *)
(*  Author:  Horsocrates | Date: February 2026                              *)
(*                                                                          *)
(*  AXIOMS: NONE. PInterval is fully constructive.                          *)
(*                                                                          *)
(*  COMPILE:                                                                *)
(*    coqc -Q . ToS PInterval.v                                             *)
(*    coqc -Q . ToS PInterval_Linear.v                                      *)
(*    coqc -Q . ToS PInterval_Conv.v                                        *)
(*    coqc -Q . ToS PInterval_Composition.v                                 *)
(*    coqc -Q . ToS PInterval_Softmax.v                                     *)
(*    coqc -Q . ToS Extraction_PInterval.v                                  *)
(*                                                                          *)
(* ========================================================================= *)

From ToS Require Import PInterval.
From ToS Require Import PInterval_Linear.
From ToS Require Import PInterval_Conv.
From ToS Require Import PInterval_Composition.
From ToS Require Import PInterval_Softmax.

Require Import ExtrOcamlBasic.
Require Import ExtrOcamlNatInt.
Require Import ExtrOcamlZInt.

(* sumbool used in Qlt_le_dec *)
Extract Inductive sumbool => "bool" [ "true" "false" ].

(* list type for dot product / sum *)
Extract Inductive list => "list" [ "[]" "(::)" ].

(* ===== Extraction ===== *)
Extraction "pinterval_verified.ml"
  (* PInterval.v: base operations *)
  pi_add
  pi_neg
  pi_sub
  pi_mul
  pi_div
  pi_relu
  pi_abs
  pi_overlaps
  pi_point
  pi_width
  pi_contains
  pi_nonzero_dec
  pi_monotone
  pi_antitone
  pi_sum
  pi_dot
  (* PInterval_Linear.v: linear layer verification *)
  pi_scale
  pi_wdot
  qdot
  weighted_width_sum
  q_l1_norm
  (* PInterval_Conv.v: conv2d + batchnorm verification *)
  pi_affine
  pi_channelwise_affine
  pi_conv_pixel
  pi_conv_channel
  (* PInterval_Composition.v: composition + re-anchoring + residual *)
  pi_midpoint
  pi_reanchor
  chain_width
  factor_product
  pi_max_pair
  pi_max_fold
  pi_residual
  (* PInterval_Softmax.v: softmax bound verification *)
  f_sum
  f_sum_except
  softmax_cross_mul_lower
  softmax_cross_mul_upper.
