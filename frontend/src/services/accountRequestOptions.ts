import { api } from "@/services/api";

export type AccountRequestScope = "HQ" | "SITE";

export interface AccountRequestSiteOption {
  id: number;
  name: string;
}

export interface AccountRequestOptions {
  departments: Record<AccountRequestScope, string[]>;
  sites: AccountRequestSiteOption[];
}

export const emptyAccountRequestOptions = (): AccountRequestOptions => ({
  departments: { HQ: [], SITE: [] },
  sites: [],
});

const koreanDepartmentCollator = new Intl.Collator("ko-KR", {
  numeric: true,
  sensitivity: "base",
});

function sortDepartmentNames(names: string[]): string[] {
  return [...names].sort((left, right) => {
    const leftIsKorean = /^[가-힣]/.test(left);
    const rightIsKorean = /^[가-힣]/.test(right);
    if (leftIsKorean !== rightIsKorean) return leftIsKorean ? -1 : 1;
    return koreanDepartmentCollator.compare(left, right);
  });
}

export async function fetchAccountRequestOptions(): Promise<AccountRequestOptions> {
  const { data } = await api.get<AccountRequestOptions>("/account-requests/public/options");
  return {
    ...data,
    departments: {
      HQ: sortDepartmentNames(data.departments.HQ),
      SITE: sortDepartmentNames(data.departments.SITE),
    },
  };
}
