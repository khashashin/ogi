import type { Entity } from "./entity";
import type { Edge } from "./edge";

export interface GraphData {
  entities: Entity[];
  edges: Edge[];
}
