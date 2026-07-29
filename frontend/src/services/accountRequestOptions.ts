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

export async function fetchAccountRequestOptions(): Promise<AccountRequestOptions> {
  const { data } = await api.get<AccountRequestOptions>("/account-requests/public/options");
  return data;
}
