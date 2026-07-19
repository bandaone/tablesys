# DATA PROCESSING AGREEMENT

**Between:**

**TABLESYS ("Processor"),** a Zambian-registered technology company

**[University Name] ("Controller"),** a higher education institution registered in Zambia

**Effective Date:** [Date of contract signature]

## 1. Definitions
| Term | Definition |
| :--- | :--- |
| **Personal Data** | Any information relating to an identified or identifiable natural person, as defined by the Zambia Data Protection Act No. 3 of 2021 |
| **Processing** | Any operation performed on personal data, including collection, storage, retrieval, and deletion |
| **Sub-processor** | Any third party engaged by TABLESYS to process personal data on behalf of the Controller |
| **Data Subject** | The individual to whom personal data relates (students, lecturers, staff) |

## 2. Scope and Purpose
TABLESYS processes personal data solely for the purpose of providing the timetable generation and management service described in the Master Services Agreement. Processing is limited to:
* Lecturer names, email addresses, and department affiliations
* Student group identifiers and enrollment counts
* Timetable slot assignments
* System audit logs

**TABLESYS does not process:**
* Student individual identities, contact details, or grades
* Financial information beyond billing contact details
* Special category data (health, biometrics, political opinions)

## 3. Controller Obligations
The Controller warrants that:
* It has a lawful basis for processing all personal data uploaded to TABLESYS
* It has obtained necessary consents from data subjects where required
* It will not upload special category data to the platform

## 4. Processor Obligations
TABLESYS shall:
* Process personal data only on documented instructions from the Controller
* Ensure all personnel with access to personal data are bound by confidentiality obligations
* Implement appropriate technical and organizational measures (per Annex A)
* Assist the Controller in responding to data subject access requests within 14 days
* Notify the Controller of any personal data breach within 72 hours of discovery
* Delete or return all personal data upon termination of the service (subject to the 30-day retention window described in the Backup and Disaster Recovery Policy)

## 5. Sub-processors
The Controller authorizes TABLESYS to engage the following sub-processors:

| Sub-processor | Purpose | Location |
| :--- | :--- | :--- |
| **Amazon Web Services / Supabase** | Cloud hosting and database | Selectable region |
| **Backblaze B2** | Encrypted backup storage | US / EU |
| **Postmark** | Transactional email delivery | US |
| **Sentry** | Error monitoring (no personal data) | US |

TABLESYS will notify the Controller of any intended changes to sub-processors at least 14 days in advance. The Controller may object within 7 days.

## 6. Data Subject Rights
TABLESYS will provide reasonable assistance to the Controller in fulfilling data subject requests (access, rectification, erasure, portability). The Controller may use the tenant data export endpoint (`GET /api/v1/export/tenant-data`) at any time to fulfill portability requests.

## 7. Security Measures (Annex A)
TABLESYS implements:
* Encryption at rest (AES-256) for all stored data
* Encryption in transit (TLS 1.3) for all API communications
* JWT-based authentication with bcrypt password hashing
* Multi-tenant data isolation at the application layer
* Audit logging of all access to personal data
* Daily encrypted backups with 30-day retention
* Rate limiting on public endpoints

## 8. Term and Termination
This DPA remains in effect for the duration of the Master Services Agreement. Upon termination, TABLESYS will:
* Deactivate the Controller's tenant immediately
* Retain data for 30 days (cooling-off period)
* Permanently purge all Controller data after 30 days unless otherwise instructed

## 9. Governing Law
This DPA is governed by the laws of the Republic of Zambia. Any disputes shall be subject to the exclusive jurisdiction of the courts of Lusaka.

**Signed:**

**TABLESYS**
Dennis Banda, Director
Date: _______________

**[University Name]**
[Name], [Title]
Date: _______________
