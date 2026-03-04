
type comparison =
| Eq
| Lt
| Gt

module Pos :
 sig
  val succ : int -> int

  val add : int -> int -> int

  val add_carry : int -> int -> int

  val pred_double : int -> int

  val mul : int -> int -> int

  val compare_cont : comparison -> int -> int -> comparison

  val compare : int -> int -> comparison
 end

module Coq_Pos :
 sig
  val succ : int -> int

  val add : int -> int -> int

  val add_carry : int -> int -> int

  val mul : int -> int -> int
 end

module Z :
 sig
  val double : int -> int

  val succ_double : int -> int

  val pred_double : int -> int

  val pos_sub : int -> int -> int

  val add : int -> int -> int

  val mul : int -> int -> int

  val compare : int -> int -> comparison
 end

val z_lt_dec : int -> int -> bool

val z_lt_ge_dec : int -> int -> bool

val z_lt_le_dec : int -> int -> bool

type q = { qnum : int; qden : int }

val qplus : q -> q -> q

val qmult : q -> q -> q

val qinv : q -> q

val qdiv : q -> q -> q

val qlt_le_dec : q -> q -> bool

val pow2 : int -> int

val qpow2 : int -> q

type realProcess = int -> q

type continuousFunction = q -> q

type bisectionState = { bis_left : q; bis_right : q }

val bisection_step : continuousFunction -> bisectionState -> bisectionState

val bisection_iter :
  continuousFunction -> bisectionState -> int -> bisectionState

val bisection_process : continuousFunction -> q -> q -> realProcess
