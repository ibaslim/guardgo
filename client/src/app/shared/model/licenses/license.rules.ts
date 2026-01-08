
export interface LicenseRuleModel {
    modules: string[] | 'all';
    cti_graph: boolean;
    mapping: boolean;
    scanning: boolean;
    maintainer: boolean;
}