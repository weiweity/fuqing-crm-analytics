import client from './index'

export interface ExportPPTParams {
  report_type: string
  start_date: string
  end_date: string
  modules: string[]
  template: string
}

export interface ExportPPTResponse {
  report_id?: string
  file_name?: string
  download_url?: string
  error?: string
}

export interface TemplatesResponse {
  templates: { id: string; name: string; description: string }[]
  modules: string[]
}

export function fetchExportTemplates(): Promise<TemplatesResponse> {
  return client.get('/v1/export/templates')
}

export function exportPPT(params: ExportPPTParams): Promise<ExportPPTResponse> {
  return client.post('/v1/export/ppt', params)
}
