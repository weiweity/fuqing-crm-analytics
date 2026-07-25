/**
 * E2E 登录凭据：CI 通过 env 注入随机密码；本地默认与常见 .env 对齐。
 * 禁止在 workflow YAML 中写死密码。
 */
export const E2E_ADMIN_USER = process.env.E2E_ADMIN_USER || 'admin'
export const E2E_ADMIN_PASSWORD =
  process.env.E2E_ADMIN_PASSWORD ||
  process.env.FQ_CRM_E2E_PASSWORD ||
  '123456'
