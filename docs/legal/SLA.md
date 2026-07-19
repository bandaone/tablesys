# SERVICE LEVEL AGREEMENT

**Provider:** TABLESYS
**Customer:** [University Name]
**Effective Date:** [Date]

## 1. Service Commitment
TABLESYS commits to **99.5% uptime** for the core timetable platform, measured monthly.

Uptime is defined as the percentage of time during a calendar month that the platform's API returns a successful response (HTTP 2xx/3xx) to authenticated requests, excluding:
* Scheduled maintenance (announced 48 hours in advance)
* Force majeure events (natural disasters, civil unrest, national internet outages)
* Customer-caused outages (invalid data uploads, exceeding quota limits)
* Third-party service outages outside TABLESYS control (university internet connectivity)

## 2. Service Credits
If uptime falls below the commitment in any calendar month, the Customer is entitled to:

| Monthly Uptime | Service Credit (% of monthly fee) |
| :--- | :--- |
| 99.0% – 99.49% | 10% |
| 98.0% – 98.99% | 25% |
| Below 98.0% | 50% |

Credits are applied to the following month's invoice. Credits do not exceed 50% of the monthly fee in any single month. To claim, the Customer must notify TABLESYS in writing within 14 days of the month in question.

## 3. Support Response Times
| Severity | Definition | Response Time | Resolution Target |
| :--- | :--- | :--- | :--- |
| **Critical (P1)** | Platform completely unavailable, all tenants affected | 1 hour | 4 hours |
| **High (P2)** | Core feature unavailable (e.g., timetable generation fails for a specific tenant) | 4 hours | 24 hours |
| **Medium (P3)** | Non-critical feature impaired (e.g., CSV export slow) | 1 business day | 5 business days |
| **Low (P4)** | Cosmetic issues, documentation errors | 3 business days | Next release |

Support is provided via email. Enterprise-tier customers receive priority phone/WhatsApp support.

## 4. Backup and Disaster Recovery
TABLESYS maintains:
* Daily automated database backups (RPO: 24 hours)
* 30-day backup retention
* Monthly restore testing
* Full disaster recovery runbook (RTO: 4 hours for full database restore)

*The complete Backup and Disaster Recovery Policy is available to customers upon request.*

## 5. Monitoring and Reporting
TABLESYS maintains a public status page at `status.tablesys.com` displaying current service status and incident history.

## 6. Limitations
This SLA applies to paid plans only. Free-tier tenants receive best-effort support with no uptime guarantee.

**Signed:**

**TABLESYS**
Dennis Banda, Director
Date: _______________

**[University Name]**
[Name], [Title]
Date: _______________
