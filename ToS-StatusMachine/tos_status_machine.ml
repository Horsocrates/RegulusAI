
(** val negb : bool -> bool **)

let negb = function
| true -> false
| false -> true

(** val length : 'a1 list -> int **)

let rec length = function
| [] -> 0
| _::l' -> succ (length l')

type comparison =
| Eq
| Lt
| Gt

(** val add : int -> int -> int **)

let rec add = (+)

module Nat =
 struct
  (** val compare : int -> int -> comparison **)

  let rec compare = fun n m -> if n=m then Eq else if n<m then Lt else Gt
 end

(** val map : ('a1 -> 'a2) -> 'a1 list -> 'a2 list **)

let rec map f = function
| [] -> []
| a::t -> (f a)::(map f t)

(** val existsb : ('a1 -> bool) -> 'a1 list -> bool **)

let rec existsb f = function
| [] -> false
| a::l0 -> (||) (f a) (existsb f l0)

(** val filter : ('a1 -> bool) -> 'a1 list -> 'a1 list **)

let rec filter f = function
| [] -> []
| x::l0 -> if f x then x::(filter f l0) else filter f l0

type entity = { entity_id : int; legacy_idx : int; structure_score : 
                int; domain_score : int }

(** val entity_id : entity -> int **)

let entity_id e =
  e.entity_id

(** val legacy_idx : entity -> int **)

let legacy_idx e =
  e.legacy_idx

(** val structure_score : entity -> int **)

let structure_score e =
  e.structure_score

(** val domain_score : entity -> int **)

let domain_score e =
  e.domain_score

type integrityGate = { eRR_complete : bool; levels_valid : bool;
                       order_valid : bool }

(** val eRR_complete : integrityGate -> bool **)

let eRR_complete i =
  i.eRR_complete

(** val levels_valid : integrityGate -> bool **)

let levels_valid i =
  i.levels_valid

(** val order_valid : integrityGate -> bool **)

let order_valid i =
  i.order_valid

type status =
| PrimaryMax
| SecondaryMax
| HistoricalMax
| Candidate
| Invalid

type policy =
| Legacy_Priority
| Recency_Priority

type diagnostic = { diag_entity_id : int; diag_gate : integrityGate;
                    diag_final_weight : int; diag_status : status;
                    diag_reason : int option }

(** val diag_entity_id : diagnostic -> int **)

let diag_entity_id d =
  d.diag_entity_id

(** val diag_gate : diagnostic -> integrityGate **)

let diag_gate d =
  d.diag_gate

(** val diag_final_weight : diagnostic -> int **)

let diag_final_weight d =
  d.diag_final_weight

(** val diag_status : diagnostic -> status **)

let diag_status d =
  d.diag_status

(** val diag_reason : diagnostic -> int option **)

let diag_reason d =
  d.diag_reason

(** val is_valid_gate : integrityGate -> bool **)

let is_valid_gate g =
  (&&) ((&&) g.eRR_complete g.levels_valid) g.order_valid

(** val failed_gate : integrityGate -> int option **)

let failed_gate g =
  if negb g.eRR_complete
  then Some (succ 0)
  else if negb g.levels_valid
       then Some (succ (succ 0))
       else if negb g.order_valid then Some (succ (succ (succ 0))) else None

(** val finalWeight : entity -> integrityGate -> int **)

let finalWeight e gate =
  if is_valid_gate gate then add e.structure_score e.domain_score else 0

(** val compare_entities :
    policy -> entity -> entity -> integrityGate -> integrityGate -> comparison **)

let compare_entities policy0 e1 e2 g1 g2 =
  let w1 = finalWeight e1 g1 in
  let w2 = finalWeight e2 g2 in
  (match Nat.compare w1 w2 with
   | Eq ->
     (match policy0 with
      | Legacy_Priority -> Nat.compare e2.legacy_idx e1.legacy_idx
      | Recency_Priority -> Nat.compare e1.legacy_idx e2.legacy_idx)
   | x -> x)

(** val beats :
    policy -> entity -> entity -> integrityGate -> integrityGate -> bool **)

let beats policy0 e1 e2 g1 g2 =
  match compare_entities policy0 e1 e2 g1 g2 with
  | Gt -> true
  | _ -> false

(** val equal_weight :
    entity -> entity -> integrityGate -> integrityGate -> bool **)

let equal_weight e1 e2 g1 g2 =
  (=) (finalWeight e1 g1) (finalWeight e2 g2)

(** val find_max_entity :
    policy -> entity list -> (entity -> integrityGate) -> entity option ->
    entity option **)

let rec find_max_entity policy0 entities gates current_max =
  match entities with
  | [] -> current_max
  | e::rest ->
    let g = gates e in
    if is_valid_gate g
    then (match current_max with
          | Some cm ->
            let gc = gates cm in
            if beats policy0 e cm g gc
            then find_max_entity policy0 rest gates (Some e)
            else find_max_entity policy0 rest gates current_max
          | None -> find_max_entity policy0 rest gates (Some e))
    else find_max_entity policy0 rest gates current_max

(** val prefixes : 'a1 list -> 'a1 list list **)

let rec prefixes = function
| [] -> []::[]
| x::rest -> []::(map (fun x0 -> x::x0) (prefixes rest))

(** val assign_status :
    policy -> entity list -> (entity -> integrityGate) -> entity -> status **)

let assign_status policy0 all_entities gates e =
  let g = gates e in
  if negb (is_valid_gate g)
  then Invalid
  else let primary = find_max_entity policy0 all_entities gates None in
       (match primary with
        | Some p ->
          let gp = gates p in
          if (=) p.entity_id e.entity_id
          then PrimaryMax
          else if equal_weight e p g gp
               then SecondaryMax
               else let proper_prefixes =
                      filter (fun pf ->
                        match pf with
                        | [] -> false
                        | _::_ -> negb ((=) (length pf) (length all_entities)))
                        (prefixes all_entities)
                    in
                    if existsb (fun pf ->
                         match find_max_entity policy0 pf gates None with
                         | Some pm -> (=) pm.entity_id e.entity_id
                         | None -> false) proper_prefixes
                    then HistoricalMax
                    else Candidate
        | None -> PrimaryMax)

(** val make_diagnostic : entity -> integrityGate -> status -> diagnostic **)

let make_diagnostic e g s =
  { diag_entity_id = e.entity_id; diag_gate = g; diag_final_weight =
    (finalWeight e g); diag_status = s; diag_reason = (failed_gate g) }

(** val diagnose_all :
    policy -> entity list -> (entity -> integrityGate) -> diagnostic list **)

let diagnose_all policy0 entities gates =
  map (fun e ->
    let g = gates e in
    let s = assign_status policy0 entities gates e in make_diagnostic e g s)
    entities
