with open("frontend/src/App.tsx", "r") as f:
    c = f.read()

c = c.replace(
    "const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));",
    "const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));\nconst BillingUsagePage = lazy(() => import('./pages/BillingUsagePage'));"
)

c = c.replace(
    "<Route path=\"lab-groups\" element={<LabGroupsPage />} />\n                  </Route>",
    "<Route path=\"lab-groups\" element={<LabGroupsPage />} />\n                    <Route path=\"billing\" element={<BillingUsagePage />} />\n                  </Route>"
)

with open("frontend/src/App.tsx", "w") as f:
    f.write(c)
