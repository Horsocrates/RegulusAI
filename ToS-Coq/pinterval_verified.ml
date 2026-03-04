
type __ = Obj.t
let __ = let rec f _ = Obj.repr f in Obj.repr f

type comparison =
| Eq
| Lt
| Gt

(** val gmax : ('a1 -> 'a1 -> comparison) -> 'a1 -> 'a1 -> 'a1 **)

let gmax cmp x y =
  match cmp x y with
  | Lt -> y
  | _ -> x

(** val gmin : ('a1 -> 'a1 -> comparison) -> 'a1 -> 'a1 -> 'a1 **)

let gmin cmp x y =
  match cmp x y with
  | Gt -> y
  | _ -> x

module Pos =
 struct
  (** val succ : int -> int **)

  let rec succ x =
    (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
      (fun p -> (fun p->2*p) (succ p))
      (fun p -> (fun p->1+2*p) p)
      (fun _ -> (fun p->2*p) 1)
      x

  (** val add : int -> int -> int **)

  let rec add x y =
    (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
      (fun p ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> (fun p->2*p) (add_carry p q0))
        (fun q0 -> (fun p->1+2*p) (add p q0))
        (fun _ -> (fun p->2*p) (succ p))
        y)
      (fun p ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> (fun p->1+2*p) (add p q0))
        (fun q0 -> (fun p->2*p) (add p q0))
        (fun _ -> (fun p->1+2*p) p)
        y)
      (fun _ ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> (fun p->2*p) (succ q0))
        (fun q0 -> (fun p->1+2*p) q0)
        (fun _ -> (fun p->2*p) 1)
        y)
      x

  (** val add_carry : int -> int -> int **)

  and add_carry x y =
    (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
      (fun p ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> (fun p->1+2*p) (add_carry p q0))
        (fun q0 -> (fun p->2*p) (add_carry p q0))
        (fun _ -> (fun p->1+2*p) (succ p))
        y)
      (fun p ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> (fun p->2*p) (add_carry p q0))
        (fun q0 -> (fun p->1+2*p) (add p q0))
        (fun _ -> (fun p->2*p) (succ p))
        y)
      (fun _ ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> (fun p->1+2*p) (succ q0))
        (fun q0 -> (fun p->2*p) (succ q0))
        (fun _ -> (fun p->1+2*p) 1)
        y)
      x

  (** val pred_double : int -> int **)

  let rec pred_double x =
    (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
      (fun p -> (fun p->1+2*p) ((fun p->2*p) p))
      (fun p -> (fun p->1+2*p) (pred_double p))
      (fun _ -> 1)
      x

  (** val mul : int -> int -> int **)

  let rec mul x y =
    (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
      (fun p -> add y ((fun p->2*p) (mul p y)))
      (fun p -> (fun p->2*p) (mul p y))
      (fun _ -> y)
      x

  (** val compare_cont : comparison -> int -> int -> comparison **)

  let rec compare_cont r x y =
    (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
      (fun p ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> compare_cont r p q0)
        (fun q0 -> compare_cont Gt p q0)
        (fun _ -> Gt)
        y)
      (fun p ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> compare_cont Lt p q0)
        (fun q0 -> compare_cont r p q0)
        (fun _ -> Gt)
        y)
      (fun _ ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun _ -> Lt)
        (fun _ -> Lt)
        (fun _ -> r)
        y)
      x

  (** val compare : int -> int -> comparison **)

  let compare =
    compare_cont Eq
 end

module Coq_Pos =
 struct
  (** val succ : int -> int **)

  let rec succ = Stdlib.Int.succ

  (** val add : int -> int -> int **)

  let rec add = (+)

  (** val add_carry : int -> int -> int **)

  and add_carry x y =
    (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
      (fun p ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> (fun p->1+2*p) (add_carry p q0))
        (fun q0 -> (fun p->2*p) (add_carry p q0))
        (fun _ -> (fun p->1+2*p) (succ p))
        y)
      (fun p ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> (fun p->2*p) (add_carry p q0))
        (fun q0 -> (fun p->1+2*p) (add p q0))
        (fun _ -> (fun p->2*p) (succ p))
        y)
      (fun _ ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> (fun p->1+2*p) (succ q0))
        (fun q0 -> (fun p->2*p) (succ q0))
        (fun _ -> (fun p->1+2*p) 1)
        y)
      x

  (** val mul : int -> int -> int **)

  let rec mul = ( * )
 end

module Z =
 struct
  (** val double : int -> int **)

  let double x =
    (fun f0 fp fn z -> if z=0 then f0 () else if z>0 then fp z else fn (-z))
      (fun _ -> 0)
      (fun p -> ((fun p->2*p) p))
      (fun p -> (~-) ((fun p->2*p) p))
      x

  (** val succ_double : int -> int **)

  let succ_double x =
    (fun f0 fp fn z -> if z=0 then f0 () else if z>0 then fp z else fn (-z))
      (fun _ -> 1)
      (fun p -> ((fun p->1+2*p) p))
      (fun p -> (~-) (Pos.pred_double p))
      x

  (** val pred_double : int -> int **)

  let pred_double x =
    (fun f0 fp fn z -> if z=0 then f0 () else if z>0 then fp z else fn (-z))
      (fun _ -> (~-) 1)
      (fun p -> (Pos.pred_double p))
      (fun p -> (~-) ((fun p->1+2*p) p))
      x

  (** val pos_sub : int -> int -> int **)

  let rec pos_sub x y =
    (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
      (fun p ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> double (pos_sub p q0))
        (fun q0 -> succ_double (pos_sub p q0))
        (fun _ -> ((fun p->2*p) p))
        y)
      (fun p ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> pred_double (pos_sub p q0))
        (fun q0 -> double (pos_sub p q0))
        (fun _ -> (Pos.pred_double p))
        y)
      (fun _ ->
      (fun f2p1 f2p f1 p ->
  if p<=1 then f1 () else if p mod 2 = 0 then f2p (p/2) else f2p1 (p/2))
        (fun q0 -> (~-) ((fun p->2*p) q0))
        (fun q0 -> (~-) (Pos.pred_double q0))
        (fun _ -> 0)
        y)
      x

  (** val add : int -> int -> int **)

  let add = (+)

  (** val opp : int -> int **)

  let opp = (~-)

  (** val mul : int -> int -> int **)

  let mul = ( * )

  (** val compare : int -> int -> comparison **)

  let compare = fun x y -> if x=y then Eq else if x<y then Lt else Gt

  (** val abs : int -> int **)

  let abs = Stdlib.Int.abs
 end

(** val z_lt_dec : int -> int -> bool **)

let z_lt_dec x y =
  match Z.compare x y with
  | Lt -> true
  | _ -> false

(** val z_lt_ge_dec : int -> int -> bool **)

let z_lt_ge_dec =
  z_lt_dec

(** val z_lt_le_dec : int -> int -> bool **)

let z_lt_le_dec =
  z_lt_ge_dec

type q = { qnum : int; qden : int }

(** val qcompare : q -> q -> comparison **)

let qcompare p q0 =
  Z.compare (Z.mul p.qnum q0.qden) (Z.mul q0.qnum p.qden)

(** val qplus : q -> q -> q **)

let qplus x y =
  { qnum = (Z.add (Z.mul x.qnum y.qden) (Z.mul y.qnum x.qden)); qden =
    (Coq_Pos.mul x.qden y.qden) }

(** val qmult : q -> q -> q **)

let qmult x y =
  { qnum = (Z.mul x.qnum y.qnum); qden = (Coq_Pos.mul x.qden y.qden) }

(** val qopp : q -> q **)

let qopp x =
  { qnum = (Z.opp x.qnum); qden = x.qden }

(** val qminus : q -> q -> q **)

let qminus x y =
  qplus x (qopp y)

(** val qinv : q -> q **)

let qinv x =
  (fun f0 fp fn z -> if z=0 then f0 () else if z>0 then fp z else fn (-z))
    (fun _ -> { qnum = 0; qden = 1 })
    (fun p -> { qnum = x.qden; qden = p })
    (fun p -> { qnum = ((~-) x.qden); qden = p })
    x.qnum

(** val qdiv : q -> q -> q **)

let qdiv x y =
  qmult x (qinv y)

(** val qlt_le_dec : q -> q -> bool **)

let qlt_le_dec x y =
  z_lt_le_dec (Z.mul x.qnum y.qden) (Z.mul y.qnum x.qden)

(** val qabs : q -> q **)

let qabs x =
  let { qnum = n; qden = d } = x in { qnum = (Z.abs n); qden = d }

(** val qmax : q -> q -> q **)

let qmax =
  gmax qcompare

(** val qmin : q -> q -> q **)

let qmin =
  gmin qcompare

type pInterval = { pi_lo : q; pi_hi : q }

type pi_contains = __

(** val pi_width : pInterval -> q **)

let pi_width i =
  qminus i.pi_hi i.pi_lo

(** val pi_point : q -> pInterval **)

let pi_point x =
  { pi_lo = x; pi_hi = x }

(** val pi_add : pInterval -> pInterval -> pInterval **)

let pi_add i j =
  { pi_lo = (qplus i.pi_lo j.pi_lo); pi_hi = (qplus i.pi_hi j.pi_hi) }

(** val pi_neg : pInterval -> pInterval **)

let pi_neg i =
  { pi_lo = (qopp i.pi_hi); pi_hi = (qopp i.pi_lo) }

(** val pi_sub : pInterval -> pInterval -> pInterval **)

let pi_sub i j =
  { pi_lo = (qminus i.pi_lo j.pi_hi); pi_hi = (qminus i.pi_hi j.pi_lo) }

(** val q_min4 : q -> q -> q -> q -> q **)

let q_min4 a b c d =
  qmin (qmin a b) (qmin c d)

(** val q_max4 : q -> q -> q -> q -> q **)

let q_max4 a b c d =
  qmax (qmax a b) (qmax c d)

(** val pi_mul : pInterval -> pInterval -> pInterval **)

let pi_mul i j =
  let ac = qmult i.pi_lo j.pi_lo in
  let ad = qmult i.pi_lo j.pi_hi in
  let bc = qmult i.pi_hi j.pi_lo in
  let bd = qmult i.pi_hi j.pi_hi in
  { pi_lo = (q_min4 ac ad bc bd); pi_hi = (q_max4 ac ad bc bd) }

(** val pi_relu : pInterval -> pInterval **)

let pi_relu i =
  { pi_lo = (qmax { qnum = 0; qden = 1 } i.pi_lo); pi_hi =
    (qmax { qnum = 0; qden = 1 } i.pi_hi) }

(** val pi_abs : pInterval -> pInterval **)

let pi_abs i =
  { pi_lo =
    (if qlt_le_dec i.pi_hi { qnum = 0; qden = 1 }
     then qopp i.pi_hi
     else if qlt_le_dec { qnum = 0; qden = 1 } i.pi_lo
          then i.pi_lo
          else { qnum = 0; qden = 1 });
    pi_hi = (qmax (qopp i.pi_lo) i.pi_hi) }

(** val pi_overlaps : pInterval -> pInterval -> bool **)

let pi_overlaps i j =
  if qlt_le_dec i.pi_hi j.pi_lo
  then false
  else if qlt_le_dec j.pi_hi i.pi_lo then false else true

(** val pi_nonzero_dec : pInterval -> bool **)

let pi_nonzero_dec i =
  if qlt_le_dec { qnum = 0; qden = 1 } i.pi_lo
  then true
  else if qlt_le_dec i.pi_hi { qnum = 0; qden = 1 } then true else false

(** val pi_div : pInterval -> pInterval -> pInterval **)

let pi_div i j =
  let inv_lo = qinv j.pi_hi in
  let inv_hi = qinv j.pi_lo in
  let ac = qmult i.pi_lo inv_lo in
  let ad = qmult i.pi_lo inv_hi in
  let bc = qmult i.pi_hi inv_lo in
  let bd = qmult i.pi_hi inv_hi in
  { pi_lo = (q_min4 ac ad bc bd); pi_hi = (q_max4 ac ad bc bd) }

(** val pi_monotone : (q -> q) -> pInterval -> pInterval **)

let pi_monotone f i =
  { pi_lo = (f i.pi_lo); pi_hi = (f i.pi_hi) }

(** val pi_antitone : (q -> q) -> pInterval -> pInterval **)

let pi_antitone f i =
  { pi_lo = (f i.pi_hi); pi_hi = (f i.pi_lo) }

(** val pi_sum : pInterval list -> pInterval **)

let rec pi_sum = function
| [] -> pi_point { qnum = 0; qden = 1 }
| x::rest -> pi_add x (pi_sum rest)

(** val pi_dot : pInterval list -> pInterval list -> pInterval **)

let rec pi_dot ws vs =
  match ws with
  | [] -> pi_point { qnum = 0; qden = 1 }
  | w::ws' ->
    (match vs with
     | [] -> pi_point { qnum = 0; qden = 1 }
     | v::vs' -> pi_add (pi_mul w v) (pi_dot ws' vs'))

(** val pi_scale : q -> pInterval -> pInterval **)

let pi_scale w x =
  { pi_lo = (qmin (qmult w x.pi_lo) (qmult w x.pi_hi)); pi_hi =
    (qmax (qmult w x.pi_lo) (qmult w x.pi_hi)) }

(** val pi_wdot : q list -> pInterval list -> pInterval **)

let rec pi_wdot ws xs =
  match ws with
  | [] -> pi_point { qnum = 0; qden = 1 }
  | w::ws' ->
    (match xs with
     | [] -> pi_point { qnum = 0; qden = 1 }
     | x::xs' -> pi_add (pi_scale w x) (pi_wdot ws' xs'))

(** val qdot : q list -> q list -> q **)

let rec qdot ws vs =
  match ws with
  | [] -> { qnum = 0; qden = 1 }
  | w::ws' ->
    (match vs with
     | [] -> { qnum = 0; qden = 1 }
     | v::vs' -> qplus (qmult w v) (qdot ws' vs'))

(** val weighted_width_sum : q list -> pInterval list -> q **)

let rec weighted_width_sum ws xs =
  match ws with
  | [] -> { qnum = 0; qden = 1 }
  | w::ws' ->
    (match xs with
     | [] -> { qnum = 0; qden = 1 }
     | x::xs' ->
       qplus (qmult (qabs w) (pi_width x)) (weighted_width_sum ws' xs'))

(** val q_l1_norm : q list -> q **)

let rec q_l1_norm = function
| [] -> { qnum = 0; qden = 1 }
| w::ws' -> qplus (qabs w) (q_l1_norm ws')

(** val pi_affine : q -> pInterval -> q -> pInterval **)

let pi_affine w x b =
  pi_add (pi_scale w x) (pi_point b)

(** val pi_channelwise_affine :
    q list -> q list -> pInterval list -> pInterval list **)

let rec pi_channelwise_affine ws bs xs =
  match ws with
  | [] -> []
  | w::ws' ->
    (match bs with
     | [] -> []
     | b::bs' ->
       (match xs with
        | [] -> []
        | x::xs' -> (pi_affine w x b)::(pi_channelwise_affine ws' bs' xs')))

(** val pi_conv_pixel : q list -> pInterval list -> q -> pInterval **)

let pi_conv_pixel ws patch b =
  pi_add (pi_wdot ws patch) (pi_point b)

(** val pi_conv_channel :
    q list -> pInterval list list -> q -> pInterval list **)

let rec pi_conv_channel ws patches b =
  match patches with
  | [] -> []
  | patch::rest -> (pi_conv_pixel ws patch b)::(pi_conv_channel ws rest b)

(** val pi_midpoint : pInterval -> q **)

let pi_midpoint i =
  qdiv (qplus i.pi_lo i.pi_hi) { qnum = ((fun p->2*p) 1); qden = 1 }

(** val pi_reanchor : pInterval -> q -> pInterval **)

let pi_reanchor i eps =
  { pi_lo = (qminus (pi_midpoint i) eps); pi_hi =
    (qplus (pi_midpoint i) eps) }

type layerSpec = q
  (* singleton inductive, whose constructor was mkLayerSpec *)

(** val chain_width : layerSpec list -> q -> q **)

let rec chain_width layers input_width =
  match layers with
  | [] -> input_width
  | l::rest -> chain_width rest (qmult l input_width)

(** val factor_product : layerSpec list -> q **)

let rec factor_product = function
| [] -> { qnum = 1; qden = 1 }
| l::rest -> qmult l (factor_product rest)

(** val pi_max_pair : pInterval -> pInterval -> pInterval **)

let pi_max_pair i j =
  { pi_lo = (qmax i.pi_lo j.pi_lo); pi_hi = (qmax i.pi_hi j.pi_hi) }

(** val pi_max_fold : pInterval -> pInterval list -> pInterval **)

let rec pi_max_fold acc = function
| [] -> acc
| x::rest -> pi_max_fold (pi_max_pair acc x) rest

(** val pi_residual : pInterval -> pInterval -> pInterval **)

let pi_residual =
  pi_add

(** val f_sum : (q -> q) -> q list -> q **)

let rec f_sum f = function
| [] -> { qnum = 0; qden = 1 }
| x::rest -> qplus (f x) (f_sum f rest)

(** val f_sum_except : (q -> q) -> q list -> int -> q **)

let rec f_sum_except f xs skip =
  match xs with
  | [] -> { qnum = 0; qden = 1 }
  | x::rest ->
    ((fun fO fS n -> if n=0 then fO () else fS (n-1))
       (fun _ -> f_sum f rest)
       (fun k -> qplus (f x) (f_sum_except f rest k))
       skip)

(** val softmax_cross_mul_lower : __ **)

let softmax_cross_mul_lower =
  __

(** val softmax_cross_mul_upper : __ **)

let softmax_cross_mul_upper =
  __
