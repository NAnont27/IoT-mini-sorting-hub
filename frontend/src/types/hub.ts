export type TargetBin = "A" | "B" | "HOLD";
export type Metric = "weight_g" | "height_mm" | "angle_deg" | "light_lux";

export interface HubConfig extends Record<string, unknown> {
  mode: "bench" | "ai";
  max_weight_g: number | null;
  max_height_mm: number | null;
  target_angles_deg: Record<TargetBin, number | null>;
}

export interface Job extends Record<string, unknown> {
  job_id: string;
  created: string;
  mode: string;
  state: string;
  target_bin?: TargetBin | null;
  result?: string | null;
  reason?: string | null;
}

export interface HubSnapshot {
  state: string;
  paused: boolean;
  job: Job | null;
  readiness_errors: string[];
  latest: Record<string, Record<string, unknown>>;
  config: HubConfig;
  influx_status: string;
  pending_command: Record<string, unknown> | null;
}

export interface History {
  source: string;
  points: { time: string; value: number }[];
}
