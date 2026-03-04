
type __ = Obj.t

type comparison =
| Eq
| Lt
| Gt

val gmax : ('a1 -> 'a1 -> comparison) -> 'a1 -> 'a1 -> 'a1

val gmin : ('a1 -> 'a1 -> comparison) -> 'a1 -> 'a1 -> 'a1

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

  val opp : int -> int

  val mul : int -> int -> int

  val compare : int -> int -> comparison

  val abs : int -> int
 end

val z_lt_dec : int -> int -> bool

val z_lt_ge_dec : int -> int -> bool

val z_lt_le_dec : int -> int -> bool

type q = { qnum : int; qden : int }

val qcompare : q -> q -> comparison

val qplus : q -> q -> q

val qmult : q -> q -> q

val qopp : q -> q

val qminus : q -> q -> q

val qinv : q -> q

val qdiv : q -> q -> q

val qlt_le_dec : q -> q -> bool

val qabs : q -> q

val qmax : q -> q -> q

val qmin : q -> q -> q

type pInterval = { pi_lo : q; pi_hi : q }

type pi_contains = __

val pi_width : pInterval -> q

val pi_point : q -> pInterval

val pi_add : pInterval -> pInterval -> pInterval

val pi_neg : pInterval -> pInterval

val pi_sub : pInterval -> pInterval -> pInterval

val q_min4 : q -> q -> q -> q -> q

val q_max4 : q -> q -> q -> q -> q

val pi_mul : pInterval -> pInterval -> pInterval

val pi_relu : pInterval -> pInterval

val pi_abs : pInterval -> pInterval

val pi_overlaps : pInterval -> pInterval -> bool

val pi_nonzero_dec : pInterval -> bool

val pi_div : pInterval -> pInterval -> pInterval

val pi_monotone : (q -> q) -> pInterval -> pInterval

val pi_antitone : (q -> q) -> pInterval -> pInterval

val pi_sum : pInterval list -> pInterval

val pi_dot : pInterval list -> pInterval list -> pInterval

val pi_scale : q -> pInterval -> pInterval

val pi_wdot : q list -> pInterval list -> pInterval

val qdot : q list -> q list -> q

val weighted_width_sum : q list -> pInterval list -> q

val q_l1_norm : q list -> q

val pi_affine : q -> pInterval -> q -> pInterval

val pi_channelwise_affine :
  q list -> q list -> pInterval list -> pInterval list

val pi_conv_pixel : q list -> pInterval list -> q -> pInterval

val pi_conv_channel : q list -> pInterval list list -> q -> pInterval list

val pi_midpoint : pInterval -> q

val pi_reanchor : pInterval -> q -> pInterval

type layerSpec = q
  (* singleton inductive, whose constructor was mkLayerSpec *)

val chain_width : layerSpec list -> q -> q

val factor_product : layerSpec list -> q

val pi_max_pair : pInterval -> pInterval -> pInterval

val pi_max_fold : pInterval -> pInterval list -> pInterval

val pi_residual : pInterval -> pInterval -> pInterval

val f_sum : (q -> q) -> q list -> q

val f_sum_except : (q -> q) -> q list -> int -> q

val softmax_cross_mul_lower : __

val softmax_cross_mul_upper : __
