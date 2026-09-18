/** Free-HTML page delivery tool contract. Browser and Host import the same constants. */

export const PAGE_GENERATE_TOOL_NAME = 'free_html_page_generate';
export const PAGE_TOOL_RESULT_SCHEMA = 'free-page-tool-result/v1';
/** Browser-minted correlation id; the tool only checks hygiene, the workbench matches exactly. */
export const PAGE_REQUEST_ID_PATTERN = /^page-gen-[A-Za-z0-9-]{8,64}$/;
