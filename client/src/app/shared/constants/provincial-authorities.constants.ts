/**
 * Canadian provincial and territorial security licensing authorities
 * Used for security license issuing authority field suggestions
 */
export const PROVINCIAL_AUTHORITIES: Record<string, string> = {
  'ON': 'Ministry of the Solicitor General',
  'AB': 'Alberta Public Safety and Emergency Services',
  'BC': 'Ministry of Public Safety and Solicitor General (Security Programs Division)',
  'QC': 'Bureau de la sécurité privée (BSP)',
  'MB': 'Manitoba Justice',
  'SK': 'Financial and Consumer Affairs Authority (FCAA)',
  'NS': 'Department of Justice (Public Safety and Security Division)',
  'NB': 'Department of Justice and Public Safety',
  'NL': 'Department of Digital Government and Service NL',
  'PE': 'Department of Justice and Public Safety (PEI Firearms Office)',
  'YT': 'Government of Yukon (Professional Licensing)',
  'NT': 'Department of Justice (Legal Registries)',
  'NU': 'Department of Justice (Legal Registries)'
};

/**
 * Get the issuing authority for a given Canadian province code
 * @param provinceCode - Two-letter province code (e.g., 'ON', 'AB')
 * @returns The issuing authority name, or empty string if not found
 */
export function getIssuingAuthorityForProvince(provinceCode: string): string {
  return provinceCode ? PROVINCIAL_AUTHORITIES[provinceCode] || '' : '';
}
