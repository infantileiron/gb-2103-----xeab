export type Role='admin'|'analyst'|'viewer';
export interface User {id:string;email:string;name:string;role:Role}
export interface Dataset {id:string;name:string;filename:string;row_count:number;sections:string[];rows?:Record<string,unknown>[]}
export interface Study {id:string;name:string;dataset_id:string;features:string[];min_k:number;max_k:number;bootstrap:number;seed:number}
export interface Point {sample_id:string;section:string;x:number;y:number;cluster:number;values:Record<string,number>}
export interface Result {selected_k:number;silhouette:number;stability:{mean_ari:number;p05:number;p95:number;replicates:number};candidates:{k:number;silhouette:number}[];profiles:{cluster_id:number;size:number;name:string;centroid:Record<string,number>}[];points:Point[];features:string[];correlation:number[][];row_count:number;seed:number;checksum:string;method:string}
export interface Run {id:string;study_id:string;status:string;result:Result|null;error:string|null;created_at:string}
export interface Profile {id:string;run_id:string;cluster_id:number;name:string;notes:string;centroid:Record<string,number>;size:number}
export interface Report {id:string;run_id:string;title:string;status:string;created_at:string;archived_by:string|null}