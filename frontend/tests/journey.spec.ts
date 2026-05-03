import { test, expect } from '@playwright/test';

test.describe('Superadmin E2E Journey', () => {
  test('Superadmin can login and view the global tenant registry', async ({ page, baseURL }) => {
    const root = (baseURL || '').trim().replace(/\/+$/, '');
    const usernameValue =
      process.env.PLAYWRIGHT_SUPERADMIN_USERNAME ||
      process.env.PLAYWRIGHT_SUPERADMIN_EMAIL ||
      'superadmin';
    const passwordValue = process.env.PLAYWRIGHT_SUPERADMIN_PASSWORD || 'K3ypAssw0rd!';

    // Deterministic auth bootstrap via the real API endpoint.
    const loginResp = await page.request.post(`${root}/api/v1/auth/login`, {
      data: { username: usernameValue, password: passwordValue }
    });
    expect(loginResp.status(), `Login failed with ${loginResp.status()}: ${await loginResp.text()}`).toBe(200);
    const loginData = await loginResp.json();
    const accessToken = loginData?.access_token as string;
    expect(accessToken).toBeTruthy();

    const meResp = await page.request.get(`${root}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` }
    });
    expect(meResp.status(), `auth/me failed with ${meResp.status()}: ${await meResp.text()}`).toBe(200);
    const meData = await meResp.json();

    // Seed frontend session exactly how AuthContext expects it.
    await page.addInitScript(
      ({ token, user }) => {
        window.sessionStorage.setItem('token', token);
        window.sessionStorage.setItem('user', JSON.stringify(user));
      },
      { token: accessToken, user: meData }
    );

    await page.goto(`${root}/superadmin`);

    // Superadmin page has stable terminal-themed headings.
    await expect(page.getByText('TableSys Core Command', { exact: false })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText('Global Tenant Registry', { exact: false })).toBeVisible({ timeout: 60_000 });

    // Basic invariant: tenant table renders (even if only tenant_id=1 exists).
    await expect(page.locator('table')).toBeVisible({ timeout: 30_000 });
  });
});
