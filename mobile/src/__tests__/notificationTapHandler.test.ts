import { handleNotificationTap } from '../notificationTapHandler';
import type { SavedAccount } from '../accounts';

describe('handleNotificationTap', () => {
  const mockGoAuth = jest.fn();
  const mockSwitchAccount = jest.fn();
  const mockSetTab = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('routes to sign-in when tapped account is not in saved list', async () => {
    const mockListAccounts = jest.fn(async () => [
      { id: 'acc1', name: 'Account 1', phone: '+919000000001', lastActiveAt: Date.now() },
    ] as SavedAccount[]);

    const data = { accountId: 'missing-account', fieldId: 'field123' };

    await handleNotificationTap(
      data,
      mockListAccounts,
      mockGoAuth,
      mockSwitchAccount,
      mockSetTab,
      'acc1',
    );

    expect(mockGoAuth).toHaveBeenCalledTimes(1);
    expect(mockSwitchAccount).not.toHaveBeenCalled();
    expect(mockSetTab).not.toHaveBeenCalled();
  });

  it('routes to sign-in when saved account list is empty', async () => {
    const mockListAccounts = jest.fn(async () => [] as SavedAccount[]);

    const data = { accountId: 'any-account', fieldId: 'field123' };

    await handleNotificationTap(
      data,
      mockListAccounts,
      mockGoAuth,
      mockSwitchAccount,
      mockSetTab,
      null,
    );

    expect(mockGoAuth).toHaveBeenCalledTimes(1);
    expect(mockSwitchAccount).not.toHaveBeenCalled();
    expect(mockSetTab).not.toHaveBeenCalled();
  });

  it('navigates to home when tapped account exists and is already active', async () => {
    const account: SavedAccount = {
      id: 'acc1',
      name: 'Account 1',
      phone: '+919000000001',
      lastActiveAt: Date.now(),
    };
    const mockListAccounts = jest.fn(async () => [account]);

    const data = { accountId: 'acc1', fieldId: 'field123' };

    await handleNotificationTap(
      data,
      mockListAccounts,
      mockGoAuth,
      mockSwitchAccount,
      mockSetTab,
      'acc1',
    );

    expect(mockSetTab).toHaveBeenCalledWith('home');
    expect(mockSwitchAccount).not.toHaveBeenCalled();
    expect(mockGoAuth).not.toHaveBeenCalled();
  });

  it('switches account before navigating to home when tapped account exists but is inactive', async () => {
    const account: SavedAccount = {
      id: 'acc2',
      name: 'Account 2',
      phone: '+919000000002',
      lastActiveAt: Date.now(),
    };
    const mockListAccounts = jest.fn(async () => [account]);

    const data = { accountId: 'acc2', fieldId: 'field123' };

    await handleNotificationTap(
      data,
      mockListAccounts,
      mockGoAuth,
      mockSwitchAccount,
      mockSetTab,
      'acc1',
    );

    expect(mockSwitchAccount).toHaveBeenCalledWith('acc2');
    expect(mockSetTab).toHaveBeenCalledWith('home');
    expect(mockGoAuth).not.toHaveBeenCalled();
  });

  it('returns early when accountId is missing from notification data', async () => {
    const mockListAccounts = jest.fn();

    const data = { fieldId: 'field123' };

    await handleNotificationTap(
      data,
      mockListAccounts,
      mockGoAuth,
      mockSwitchAccount,
      mockSetTab,
      'acc1',
    );

    expect(mockListAccounts).not.toHaveBeenCalled();
    expect(mockGoAuth).not.toHaveBeenCalled();
    expect(mockSetTab).not.toHaveBeenCalled();
  });

  it('returns early when fieldId is missing from notification data', async () => {
    const mockListAccounts = jest.fn();

    const data = { accountId: 'acc1' };

    await handleNotificationTap(
      data,
      mockListAccounts,
      mockGoAuth,
      mockSwitchAccount,
      mockSetTab,
      'acc1',
    );

    expect(mockListAccounts).not.toHaveBeenCalled();
    expect(mockGoAuth).not.toHaveBeenCalled();
    expect(mockSetTab).not.toHaveBeenCalled();
  });

  it('handles switchAccount error gracefully and still navigates to home', async () => {
    const account: SavedAccount = {
      id: 'acc2',
      name: 'Account 2',
      phone: '+919000000002',
      lastActiveAt: Date.now(),
    };
    const mockListAccounts = jest.fn(async () => [account]);
    const mockSwitchAccountError = jest.fn(async () => {
      throw new Error('Switch failed');
    });

    const data = { accountId: 'acc2', fieldId: 'field123' };

    await handleNotificationTap(
      data,
      mockListAccounts,
      mockGoAuth,
      mockSwitchAccountError,
      mockSetTab,
      'acc1',
    );

    expect(mockSwitchAccountError).toHaveBeenCalledWith('acc2');
    expect(mockSetTab).toHaveBeenCalledWith('home');
    expect(mockGoAuth).not.toHaveBeenCalled();
  });
});
