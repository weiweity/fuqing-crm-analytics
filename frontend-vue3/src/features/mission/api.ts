import client from '@/api'

export type MissionStatus =
  | 'AWAITING_APPROVAL'
  | 'APPROVED'
  | 'WAITING_MEASUREMENT'

export interface DataProvenance {
  data_profile: 'synthetic'
  contains_real_data: false
  dataset_version: string
  dataset_content_sha256: string
  analysis_as_of_date: string
  metric_versions: string[]
}

export interface ChannelMetric {
  channel: string
  first_paid_customers: number
  mature_30d_customers: number
  second_paid_rate_30d: number
  median_days_to_second_paid: number | null
  cross_channel_rate: number
  avg_net_value_180d: number
}

export interface Mission {
  mission_id: string
  status: MissionStatus
  version: number
  title: string
  executive_summary: string
  recommendation: string
  decision: {
    decision_type: string
    volume_leader: string
    quality_leader: string
    guardrail: string
    next_action: string
  }
  channel_metrics: ChannelMetric[]
  target_audience: {
    segment_key: string
    segment_name: string
    channel: string
    lifecycle_stage: string
    eligible_customers: number
    activation_product: {
      product_code: string
      product_name: string
      list_price: number
      synthetic_unit_cost: number
      replenishment_cycle_days: number
    }
  }
  economics: {
    experiment_share: number
    holdout_share: number
    assumed_conversion_uplift: number
    expected_incremental_customers: number
    expected_incremental_margin: number
    currency: string
    assumption_note: string
  }
  evidence: Array<{ metric: string; finding: string; metric_version: string }>
  state_timeline: Array<{ state: string; reached: boolean }>
  approval: { approved_by: string; approved_at: string } | null
  latest_export: DraftExport | null
  demo_controls: { reset_enabled: boolean }
  data_provenance: DataProvenance
}

export interface Diagnosis {
  question: string
  intent: string
  answer_mode: 'DETERMINISTIC_TOOL'
  answer: string
  evidence: Array<Record<string, unknown>>
  limitations: string[]
  data_provenance: DataProvenance
}

export interface DraftExport {
  mission_id: string
  mission_status: 'WAITING_MEASUREMENT'
  mission_version: number
  export_id: string
  export_status: 'DRAFT_EXPORT_READY'
  row_count: number
  experiment_count: number
  holdout_count: number
  sha256: string
  download_url: string
  expires_at: null
  data_provenance: DataProvenance
}

export async function getTodayMission(): Promise<Mission> {
  return await client.get<Mission>('/v1/missions/today') as unknown as Mission
}

export async function diagnoseMission(question: string): Promise<Diagnosis> {
  return await client.post<Diagnosis>('/v1/missions/diagnose', {
    question,
  }) as unknown as Diagnosis
}

export async function approveMission(
  missionId: string,
  version: number,
  idempotencyKey: string,
): Promise<Mission> {
  return await client.post<Mission>(
    `/v1/missions/${missionId}/approve`,
    { decision: 'APPROVE', note: '同意生成合成数据草稿名单' },
    {
      headers: {
        'If-Match': String(version),
        'Idempotency-Key': idempotencyKey,
      },
    },
  ) as unknown as Mission
}

export async function createDraftExport(
  missionId: string,
  version: number,
  idempotencyKey: string,
): Promise<DraftExport> {
  return await client.post<DraftExport>(
    `/v1/missions/${missionId}/audience-export`,
    undefined,
    {
      headers: {
        'If-Match': String(version),
        'Idempotency-Key': idempotencyKey,
      },
    },
  ) as unknown as DraftExport
}

export async function resetMission(
  missionId: string,
  version: number,
  idempotencyKey: string,
): Promise<Mission> {
  return await client.post<Mission>(
    `/v1/missions/${missionId}/demo-reset`,
    undefined,
    {
      headers: {
        'If-Match': String(version),
        'Idempotency-Key': idempotencyKey,
      },
    },
  ) as unknown as Mission
}

export async function downloadDraftExport(draft: DraftExport): Promise<void> {
  const blob = await client.get<Blob>(draft.download_url.replace(/^\/api/, ''), {
    responseType: 'blob',
  }) as unknown as Blob
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${draft.export_id}.csv`
  anchor.click()
  URL.revokeObjectURL(url)
}
