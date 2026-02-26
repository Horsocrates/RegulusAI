(* ========================================================================= *)
(*  Extraction: IVT + Archimedean -> OCaml                                  *)
(*  Part of: Regulus Phase 1 - Verified AI Computation                      *)
(*                                                                          *)
(*  Author:  Horsocrates | Date: February 2026                              *)
(*                                                                          *)
(*  PURPOSE:                                                                *)
(*    Extract computationally pure functions from IVT_ERR.v and             *)
(*    Archimedean_ERR.v into OCaml code.                                    *)
(*                                                                          *)
(*  DEPENDENCY AUDIT:                                                       *)
(*    - Qpow2            : NO axioms (pure Q arithmetic)                    *)
(*    - bisection_step   : uses Qlt_le_dec (decidable), NO classic          *)
(*    - bisection_iter   : recursion over bisection_step, NO classic        *)
(*    - bisection_process: wrapper, NO classic                              *)
(*    - IVT_process      : uses classic (existential) - NOT extracted       *)
(*                                                                          *)
(*  COMPILE:                                                                *)
(*    coqc -Q . ToS Archimedean.v                                           *)
(*    coqc -Q . ToS IVT.v                                                   *)
(*    coqc -Q . ToS Extraction_IVT.v                                        *)
(*                                                                          *)
(* ========================================================================= *)

From ToS Require Import Archimedean.
From ToS Require Import IVT.

Require Import ExtrOcamlBasic.
Require Import ExtrOcamlNatInt.
Require Import ExtrOcamlZInt.

(* ===== Dependency audit ===== *)
(* Uncomment to verify at compile time: *)
(* Print Assumptions Qpow2.            (* Expected: Closed under the global context *) *)
(* Print Assumptions bisection_step.    (* Expected: Closed under the global context *) *)
(* Print Assumptions bisection_iter.    (* Expected: Closed under the global context *) *)
(* Print Assumptions bisection_process. (* Expected: Closed under the global context *) *)
(* Print Assumptions IVT_process.       (* Expected: classic *) *)

(* ===== Type mappings ===== *)
(* ExtrOcamlBasic handles: bool, sumbool, option, unit, prod, list *)
(* ExtrOcamlNatInt handles: nat -> int *)
(* ExtrOcamlZInt handles: Z -> int, positive -> int *)

(* Additional mappings for sumbool (used by Qlt_le_dec) *)
Extract Inductive sumbool => "bool" [ "true" "false" ].

(* ===== Extraction target ===== *)
(* Extract only computationally pure functions: *)
(*   - Qpow2: 2^n as rational *)
(*   - pow2: 2^n as positive *)
(*   - bisection_step: one step of bisection *)
(*   - bisection_iter: n steps of bisection *)
(*   - bisection_process: full RealProcess from bisection *)
(*   - BisectionState: record type *)

Extraction "ivt_verified.ml"
  pow2
  Qpow2
  bisection_step
  bisection_iter
  bisection_process.
