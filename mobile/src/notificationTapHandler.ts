import type { SavedAccount } from './accounts';

export async function handleNotificationTap(
  data: any,
  listAccounts: () => Promise<SavedAccount[]>,
  goAuth: () => Promise<void>,
  switchAccount: (id: string) => Promise<void>,
  setTab: (tab: string) => void,
  activeAccountId: string | null,
): Promise<void> {
  const tapAccountId = data?.accountId;
  const tapFieldId = data?.fieldId;
  if (!tapAccountId || !tapFieldId) return;

  const saved = await listAccounts();
  const account = saved.find((a) => a.id === tapAccountId);
  if (!account) {
    await goAuth();
    return;
  }

  if (account.id !== activeAccountId) {
    try {
      await switchAccount(account.id);
    } catch {}
  }

  setTab('home');
}
