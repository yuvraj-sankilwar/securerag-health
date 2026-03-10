"""Seed initial data: roles, demo tenant, demo users, and demo documents."""

import asyncio
import logging
import uuid

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, Tenant, User
from app.authz.permissions import get_roles_for_doc_type
from app.config import settings
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─────────────────────────────────────────────────────────────────
# Role definitions
# ─────────────────────────────────────────────────────────────────
ROLES = [
    {"name": "PHYSICIAN", "description": "Medical doctor with full clinical access"},
    {"name": "NURSE", "description": "Registered nurse with patient care access"},
    {"name": "RADIOLOGIST", "description": "Imaging specialist with radiology access"},
    {"name": "PHARMACIST", "description": "Pharmacist with drug and prescription access"},
    {"name": "PATIENT", "description": "Patient with access to own records only"},
    {"name": "LAB_TECHNICIAN", "description": "Lab technician with lab order and specimen access"},
    {"name": "ADMINISTRATOR", "description": "Hospital administrator with billing and HR access"},
    {"name": "COMPLIANCE_OFFICER", "description": "Compliance officer with audit and regulatory access"},
]

# ─────────────────────────────────────────────────────────────────
# Demo tenant
# ─────────────────────────────────────────────────────────────────
DEMO_TENANT = {
    "name": "City General Hospital - Cardiology",
    "department_code": "CARDIO-001",
}

# ─────────────────────────────────────────────────────────────────
# Demo users (one per role)
# ─────────────────────────────────────────────────────────────────
DEMO_USERS = [
    {"email": "dr.smith@hospital.com", "full_name": "Dr. Sarah Smith", "role_name": "PHYSICIAN"},
    {"email": "nurse.jones@hospital.com", "full_name": "Nurse Jane Jones", "role_name": "NURSE"},
    {"email": "rad.patel@hospital.com", "full_name": "Dr. Raj Patel", "role_name": "RADIOLOGIST"},
    {"email": "pharm.wilson@hospital.com", "full_name": "Pharmacist Tom Wilson", "role_name": "PHARMACIST"},
    {"email": "patient.001@hospital.com", "full_name": "John Doe (Patient)", "role_name": "PATIENT"},
    {"email": "lab.chen@hospital.com", "full_name": "Lab Tech Wei Chen", "role_name": "LAB_TECHNICIAN"},
    {"email": "admin.taylor@hospital.com", "full_name": "Admin Lisa Taylor", "role_name": "ADMINISTRATOR"},
    {"email": "compliance.moore@hospital.com", "full_name": "Officer David Moore", "role_name": "COMPLIANCE_OFFICER"},
]

DEMO_PASSWORD = "Demo@1234"

# ─────────────────────────────────────────────────────────────────
# Demo documents — realistic medical content for each type
# ─────────────────────────────────────────────────────────────────
DEMO_DOCUMENTS = [
    {
        "title": "EHR - Patient John Doe - Cardiac Assessment",
        "doc_type": "EHR",
        "sensitivity_tier": 3,
        "content": (
            "Patient: John Doe (ID: P-001)\n"
            "Date: 2024-03-15\n"
            "Department: Cardiology\n\n"
            "Chief Complaint: Patient presents with intermittent chest pain, radiating to the left arm, "
            "occurring during physical exertion. Duration: 2 weeks.\n\n"
            "History of Present Illness: 58-year-old male with a history of hypertension and "
            "hyperlipidemia. Reports chest tightness during moderate exercise. No syncope or dyspnea "
            "at rest. Family history significant for coronary artery disease (father, MI at age 62).\n\n"
            "Vital Signs:\n"
            "- BP: 142/88 mmHg\n"
            "- HR: 78 bpm, regular\n"
            "- RR: 16 breaths/min\n"
            "- Temp: 98.6°F\n"
            "- SpO2: 97% on room air\n\n"
            "Physical Examination:\n"
            "- Cardiovascular: S1, S2 normal. No murmurs, rubs, or gallops.\n"
            "- Lungs: Clear to auscultation bilaterally.\n"
            "- Extremities: No edema, pulses 2+ bilaterally.\n\n"
            "Assessment: Suspected stable angina pectoris. Rule out acute coronary syndrome.\n\n"
            "Plan:\n"
            "1. 12-lead ECG — completed, showing nonspecific ST changes\n"
            "2. Troponin levels — pending\n"
            "3. Stress echocardiogram scheduled\n"
            "4. Start aspirin 81mg daily\n"
            "5. Continue lisinopril 20mg, atorvastatin 40mg\n"
            "6. Cardiology follow-up in 1 week"
        ),
        "authorized_roles_override": ["PHYSICIAN", "NURSE"],
        "user_email": "dr.smith@hospital.com",
    },
    {
        "title": "EHR - Patient Jane Williams - Hypertension Follow-up",
        "doc_type": "EHR",
        "sensitivity_tier": 3,
        "content": (
            "Patient: Jane Williams (ID: P-045)\n"
            "Date: 2024-03-18\n"
            "Department: Cardiology\n\n"
            "Follow-up Visit — Hypertension Management\n\n"
            "Current Medications:\n"
            "- Amlodipine 10mg daily\n"
            "- Hydrochlorothiazide 25mg daily\n"
            "- Metoprolol succinate 50mg daily\n\n"
            "Blood Pressure Log (past 2 weeks):\n"
            "- Average: 136/82 mmHg (home monitoring)\n"
            "- Office reading: 140/85 mmHg\n\n"
            "Labs: BMP within normal limits. Creatinine 0.9 mg/dL. Potassium 4.2 mEq/L.\n\n"
            "Assessment: Hypertension not at goal (<130/80). Consider ACE inhibitor substitution.\n"
            "Plan: Switch amlodipine to lisinopril 20mg. Recheck in 4 weeks."
        ),
        "authorized_roles_override": ["PHYSICIAN", "NURSE"],
        "user_email": "dr.smith@hospital.com",
    },
    {
        "title": "Radiology Report - Chest X-Ray PA/Lateral",
        "doc_type": "RADIOLOGY_REPORT",
        "sensitivity_tier": 2,
        "content": (
            "RADIOLOGY REPORT\n"
            "Examination: Chest X-Ray, PA and Lateral views\n"
            "Patient: John Doe (ID: P-001)\n"
            "Date: 2024-03-15\n"
            "Referring Physician: Dr. Sarah Smith\n\n"
            "Clinical Indication: Chest pain, rule out pulmonary pathology.\n\n"
            "Findings:\n"
            "- Heart size: Upper limits of normal. Cardiothoracic ratio 0.50.\n"
            "- Mediastinum: Normal mediastinal contour. No widening.\n"
            "- Lungs: Clear bilaterally. No focal consolidation, effusion, or pneumothorax.\n"
            "- Pleural spaces: No effusion.\n"
            "- Osseous structures: Mild degenerative changes of the thoracic spine.\n"
            "- Soft tissues: Unremarkable.\n\n"
            "Impression:\n"
            "1. Borderline cardiomegaly. Recommend echocardiogram for further evaluation.\n"
            "2. No acute cardiopulmonary process identified.\n\n"
            "Reported by: Dr. Raj Patel, MD Radiology\n"
            "Electronically signed: 2024-03-15 14:30"
        ),
        "authorized_roles_override": ["PHYSICIAN", "RADIOLOGIST"],
        "user_email": "rad.patel@hospital.com",
    },
    {
        "title": "Radiology Report - CT Coronary Angiography",
        "doc_type": "RADIOLOGY_REPORT",
        "sensitivity_tier": 3,
        "content": (
            "RADIOLOGY REPORT\n"
            "Examination: CT Coronary Angiography (CTA)\n"
            "Patient: Jane Williams (ID: P-045)\n"
            "Date: 2024-03-20\n\n"
            "Clinical Indication: Atypical chest pain, CAD risk stratification.\n\n"
            "Technique: ECG-gated CTA with 80mL Omnipaque 350 IV contrast.\n\n"
            "Findings:\n"
            "- Left Main: No stenosis.\n"
            "- LAD: Mild calcified plaque in proximal segment. <30% stenosis.\n"
            "- LCx: No significant disease.\n"
            "- RCA: Mild non-calcified plaque. <25% stenosis.\n"
            "- Aortic root: Normal diameter (3.2cm).\n"
            "- Calcium Score: 85 Agatston units (moderate).\n\n"
            "Impression:\n"
            "1. Mild non-obstructive coronary artery disease.\n"
            "2. Calcium score indicates moderate cardiovascular risk.\n"
            "3. Recommend aggressive risk factor modification.\n\n"
            "Reported by: Dr. Raj Patel, MD Radiology"
        ),
        "authorized_roles_override": ["PHYSICIAN", "RADIOLOGIST"],
        "user_email": "rad.patel@hospital.com",
    },
    {
        "title": "Drug Formulary - Cardiovascular Medications",
        "doc_type": "DRUG_FORMULARY",
        "sensitivity_tier": 1,
        "content": (
            "HOSPITAL DRUG FORMULARY — Cardiovascular Section\n"
            "Effective Date: 2024-01-01\n\n"
            "1. ACE Inhibitors:\n"
            "   - Lisinopril 5mg, 10mg, 20mg, 40mg tablets\n"
            "   - Enalapril 2.5mg, 5mg, 10mg, 20mg tablets\n"
            "   - Ramipril 2.5mg, 5mg, 10mg capsules\n\n"
            "2. Beta-Blockers:\n"
            "   - Metoprolol succinate 25mg, 50mg, 100mg, 200mg ER tablets\n"
            "   - Atenolol 25mg, 50mg, 100mg tablets\n"
            "   - Carvedilol 3.125mg, 6.25mg, 12.5mg, 25mg tablets\n\n"
            "3. Calcium Channel Blockers:\n"
            "   - Amlodipine 2.5mg, 5mg, 10mg tablets\n"
            "   - Diltiazem ER 120mg, 180mg, 240mg, 360mg capsules\n\n"
            "4. Antiplatelet Agents:\n"
            "   - Aspirin 81mg, 325mg tablets\n"
            "   - Clopidogrel 75mg tablets\n"
            "   - Ticagrelor 60mg, 90mg tablets\n\n"
            "5. Statins:\n"
            "   - Atorvastatin 10mg, 20mg, 40mg, 80mg tablets\n"
            "   - Rosuvastatin 5mg, 10mg, 20mg, 40mg tablets\n\n"
            "Note: All formulary substitutions must be approved by attending physician. "
            "Generic equivalents preferred unless brand-specific indication exists."
        ),
        "authorized_roles_override": ["PHARMACIST", "PHYSICIAN"],
        "user_email": "pharm.wilson@hospital.com",
    },
    {
        "title": "Drug Formulary - Anticoagulants and Thrombolytics",
        "doc_type": "DRUG_FORMULARY",
        "sensitivity_tier": 1,
        "content": (
            "HOSPITAL DRUG FORMULARY — Anticoagulants Section\n"
            "Effective Date: 2024-01-01\n\n"
            "1. Direct Oral Anticoagulants (DOACs):\n"
            "   - Apixaban (Eliquis) 2.5mg, 5mg tablets\n"
            "   - Rivaroxaban (Xarelto) 10mg, 15mg, 20mg tablets\n"
            "   - Dabigatran (Pradaxa) 75mg, 150mg capsules\n\n"
            "2. Heparins:\n"
            "   - Unfractionated heparin 1000units/mL, 5000units/mL vials\n"
            "   - Enoxaparin (Lovenox) 30mg, 40mg, 60mg, 80mg, 100mg syringes\n\n"
            "3. Vitamin K Antagonists:\n"
            "   - Warfarin 1mg, 2mg, 2.5mg, 3mg, 4mg, 5mg, 7.5mg, 10mg tablets\n\n"
            "Drug Interaction Alerts:\n"
            "- DOACs + strong CYP3A4 inhibitors: CONTRAINDICATED\n"
            "- Warfarin + NSAIDs: Increased bleeding risk\n"
            "- Heparin + platelet inhibitors: Monitor closely"
        ),
        "authorized_roles_override": ["PHARMACIST", "PHYSICIAN"],
        "user_email": "pharm.wilson@hospital.com",
    },
    {
        "title": "Lab Order - Complete Blood Count and Metabolic Panel",
        "doc_type": "LAB_ORDER",
        "sensitivity_tier": 2,
        "content": (
            "LABORATORY ORDER\n"
            "Order ID: LAB-2024-0315-001\n"
            "Patient: John Doe (ID: P-001)\n"
            "Ordering Physician: Dr. Sarah Smith\n"
            "Date: 2024-03-15\n"
            "Priority: Routine\n\n"
            "Tests Ordered:\n"
            "1. Complete Blood Count (CBC) with Differential\n"
            "2. Comprehensive Metabolic Panel (CMP)\n"
            "3. Troponin I (serial, q6h x 3)\n"
            "4. BNP (B-type Natriuretic Peptide)\n"
            "5. Lipid Panel (fasting)\n"
            "6. HbA1c\n\n"
            "Results (CBC):\n"
            "- WBC: 7.2 x10^9/L (normal: 4.5-11.0)\n"
            "- RBC: 4.8 x10^12/L (normal: 4.5-5.5)\n"
            "- Hemoglobin: 14.2 g/dL (normal: 13.5-17.5)\n"
            "- Hematocrit: 42% (normal: 38-50%)\n"
            "- Platelets: 245 x10^9/L (normal: 150-400)\n\n"
            "Results (Troponin):\n"
            "- T+0h: 0.02 ng/mL (normal: <0.04) — NEGATIVE\n"
            "- T+6h: 0.03 ng/mL — NEGATIVE\n"
            "- T+12h: 0.02 ng/mL — NEGATIVE\n\n"
            "Interpretation: Serial troponins negative. Low probability of acute MI."
        ),
        "authorized_roles_override": ["LAB_TECHNICIAN", "PHYSICIAN"],
        "user_email": "lab.chen@hospital.com",
    },
    {
        "title": "Lab Order - Coagulation Studies",
        "doc_type": "LAB_ORDER",
        "sensitivity_tier": 2,
        "content": (
            "LABORATORY ORDER\n"
            "Order ID: LAB-2024-0318-004\n"
            "Patient: Jane Williams (ID: P-045)\n"
            "Ordering Physician: Dr. Sarah Smith\n"
            "Date: 2024-03-18\n"
            "Priority: STAT\n\n"
            "Tests Ordered:\n"
            "1. PT/INR\n"
            "2. aPTT\n"
            "3. D-dimer\n"
            "4. Fibrinogen level\n\n"
            "Results:\n"
            "- PT: 12.5 seconds (normal: 11-13.5)\n"
            "- INR: 1.0 (normal: 0.8-1.2)\n"
            "- aPTT: 29 seconds (normal: 25-35)\n"
            "- D-dimer: 0.3 mg/L FEU (normal: <0.5)\n"
            "- Fibrinogen: 280 mg/dL (normal: 200-400)\n\n"
            "Interpretation: Coagulation studies within normal limits. "
            "No evidence of disseminated intravascular coagulopathy.\n"
            "Safe to initiate prophylactic anticoagulation if indicated."
        ),
        "authorized_roles_override": ["LAB_TECHNICIAN", "PHYSICIAN"],
        "user_email": "lab.chen@hospital.com",
    },
    {
        "title": "Billing Record - Patient John Doe - March 2024",
        "doc_type": "BILLING_RECORD",
        "sensitivity_tier": 2,
        "content": (
            "BILLING SUMMARY\n"
            "Account: BIL-2024-P001\n"
            "Patient: John Doe (ID: P-001)\n"
            "Period: March 2024\n"
            "Insurance: BlueCross BlueShield PPO\n"
            "Member ID: BCBS-887654321\n\n"
            "Charges:\n"
            "1. Office Visit - Level 4 (99214): $250.00\n"
            "2. 12-Lead ECG (93000): $85.00\n"
            "3. Chest X-Ray PA/Lateral (71046): $175.00\n"
            "4. CBC with Diff (85025): $45.00\n"
            "5. CMP (80053): $55.00\n"
            "6. Troponin I x3 (84484): $120.00\n"
            "7. BNP (83880): $95.00\n"
            "8. Lipid Panel (80061): $65.00\n"
            "9. Stress Echo (93351): $450.00\n\n"
            "Total Charges: $1,340.00\n"
            "Insurance Allowed: $987.50\n"
            "Patient Co-pay: $40.00\n"
            "Patient Responsibility: $352.50\n"
            "Balance Due: $352.50\n\n"
            "Payment Status: Claim submitted to BCBS on 2024-03-20. Pending adjudication."
        ),
        "authorized_roles_override": ["ADMINISTRATOR"],
        "user_email": "admin.taylor@hospital.com",
    },
    {
        "title": "Billing Record - Department Revenue Summary Q1 2024",
        "doc_type": "BILLING_RECORD",
        "sensitivity_tier": 2,
        "content": (
            "DEPARTMENT REVENUE SUMMARY\n"
            "Department: Cardiology (CARDIO-001)\n"
            "Quarter: Q1 2024 (January - March)\n\n"
            "Summary:\n"
            "- Total Patient Encounters: 1,245\n"
            "- Total Charges Billed: $2,850,000\n"
            "- Total Collections: $2,100,000\n"
            "- Collection Rate: 73.7%\n"
            "- Outstanding AR: $482,000\n"
            "- Write-offs: $268,000\n\n"
            "Top Revenue Procedures:\n"
            "1. Cardiac Catheterization: $680,000 (23.9%)\n"
            "2. Echocardiography: $425,000 (14.9%)\n"
            "3. Stress Testing: $350,000 (12.3%)\n"
            "4. Office Visits: $310,000 (10.9%)\n"
            "5. Holter Monitoring: $185,000 (6.5%)\n\n"
            "Payer Mix:\n"
            "- Medicare: 45%\n"
            "- Private Insurance: 38%\n"
            "- Medicaid: 12%\n"
            "- Self-Pay: 5%"
        ),
        "authorized_roles_override": ["ADMINISTRATOR"],
        "user_email": "admin.taylor@hospital.com",
    },
    {
        "title": "Compliance Audit Log - Q1 2024 HIPAA Review",
        "doc_type": "AUDIT_LOG",
        "sensitivity_tier": 4,
        "content": (
            "COMPLIANCE AUDIT REPORT\n"
            "Period: Q1 2024\n"
            "Department: Cardiology (CARDIO-001)\n"
            "Prepared by: David Moore, Compliance Officer\n"
            "Date: 2024-04-01\n\n"
            "HIPAA Compliance Summary:\n\n"
            "1. Access Control Review:\n"
            "   - Total EHR access events: 15,432\n"
            "   - Flagged unauthorized access attempts: 3\n"
            "   - All flagged events investigated and resolved\n"
            "   - Break-the-glass events: 2 (both documented and justified)\n\n"
            "2. PHI Breach Assessment:\n"
            "   - Reported incidents: 0\n"
            "   - Near-miss events: 1 (misdirected fax, intercepted before delivery)\n\n"
            "3. Training Compliance:\n"
            "   - Annual HIPAA training completion: 98%\n"
            "   - Outstanding: 3 employees (new hires, scheduled by April 15)\n\n"
            "4. Risk Assessment:\n"
            "   - Encryption status: All data at rest and in transit — COMPLIANT\n"
            "   - Backup procedures: Tested monthly — COMPLIANT\n"
            "   - Business Associate Agreements: All current — COMPLIANT\n\n"
            "Recommendations:\n"
            "- Implement automated PHI access anomaly detection\n"
            "- Update breach notification procedures per 2024 guidance\n"
            "- Schedule penetration testing for Q2 2024"
        ),
        "authorized_roles_override": ["COMPLIANCE_OFFICER"],
        "user_email": "compliance.moore@hospital.com",
    },
    {
        "title": "Compliance Audit Log - Data Retention Policy Review",
        "doc_type": "AUDIT_LOG",
        "sensitivity_tier": 4,
        "content": (
            "DATA RETENTION POLICY REVIEW\n"
            "Review Date: 2024-03-25\n"
            "Reviewer: David Moore, Compliance Officer\n\n"
            "Current Retention Periods:\n"
            "- Medical Records: 10 years from last encounter (state minimum: 7 years)\n"
            "- Billing Records: 7 years\n"
            "- Imaging Studies: 10 years (5 years for pediatric, until age 21)\n"
            "- Lab Results: 10 years\n"
            "- Audit Logs: 6 years\n"
            "- Employee Records: 7 years post-separation\n\n"
            "Findings:\n"
            "1. 245 records approaching retention deadline (due for archival by June 2024)\n"
            "2. All records properly indexed and retrievable\n"
            "3. Cloud backup retention aligned with policy\n"
            "4. WORM storage compliance verified for regulatory records\n\n"
            "Action Items:\n"
            "- Schedule Q2 archival batch for 245 expiring records\n"
            "- Update policy to reflect new CMS interoperability requirements\n"
            "- Review cloud vendor retention capabilities"
        ),
        "authorized_roles_override": ["COMPLIANCE_OFFICER"],
        "user_email": "compliance.moore@hospital.com",
    },
    {
        "title": "OWN EHR Summary - Patient John Doe",
        "doc_type": "OWN_EHR_SUMMARY",
        "sensitivity_tier": 2,
        "content": (
            "PATIENT HEALTH SUMMARY\n"
            "Patient: John Doe\n"
            "Date Generated: 2024-03-16\n\n"
            "Active Conditions:\n"
            "- Essential hypertension (I10)\n"
            "- Hyperlipidemia (E78.5)\n"
            "- Stable angina pectoris — under evaluation (I20.8)\n\n"
            "Current Medications:\n"
            "1. Lisinopril 20mg — Take one tablet daily for blood pressure\n"
            "2. Atorvastatin 40mg — Take one tablet at bedtime for cholesterol\n"
            "3. Aspirin 81mg — Take one tablet daily (newly started)\n\n"
            "Recent Appointments:\n"
            "- March 15, 2024: Cardiology visit with Dr. Smith\n"
            "  Reason: Chest pain evaluation\n"
            "  Outcome: ECG performed, lab work ordered, stress test scheduled\n\n"
            "Upcoming Appointments:\n"
            "- March 22, 2024: Stress echocardiogram\n"
            "- March 29, 2024: Follow-up with Dr. Smith\n\n"
            "Immunizations:\n"
            "- Flu vaccine: 2023-10-15\n"
            "- COVID-19 booster: 2023-09-20\n"
            "- Tdap: 2020-05-10\n\n"
            "Allergies:\n"
            "- Penicillin (rash)\n"
            "- Sulfa drugs (urticaria)"
        ),
        "authorized_roles_override": ["PATIENT"],
        "is_patient_owned": True,
        "user_email": "patient.001@hospital.com",
    },
    {
        "title": "Discharge Notes - Patient John Doe",
        "doc_type": "OWN_EHR_SUMMARY",
        "sensitivity_tier": 2,
        "content": (
            "DISCHARGE SUMMARY\n"
            "Patient: John Doe\n"
            "Date: 2024-03-22\n\n"
            "Hospital Course:\n"
            "Patient was admitted for cardiac evaluation due to exertional chest pain. "
            "Serial troponins were negative. Stress echocardiogram showed no inducible ischemia. "
            "CT Coronary Angiography revealed mild non-obstructive CAD.\n\n"
            "Discharge Diagnosis:\n"
            "- Non-obstructive coronary artery disease\n"
            "- Stable angina, resolved with medical management\n\n"
            "Discharge Medications:\n"
            "1. Lisinopril 20mg daily\n"
            "2. Atorvastatin 40mg at bedtime\n"
            "3. Aspirin 81mg daily\n"
            "4. Metoprolol succinate 25mg daily (NEW)\n\n"
            "Follow-up Instructions:\n"
            "- Cardiology follow-up in 2 weeks\n"
            "- Continue home blood pressure monitoring\n"
            "- Report any recurrence of chest pain immediately\n"
            "- Cardiac rehabilitation referral placed\n"
            "- Diet: Heart-healthy, low sodium (<2g/day)"
        ),
        "authorized_roles_override": ["PATIENT"],
        "is_patient_owned": True,
        "user_email": "patient.001@hospital.com",
    },
]


async def seed_initial_data(db: AsyncSession) -> None:
    """
    Seed the database with initial roles, demo tenant, users, and documents.

    This function is idempotent — it checks for existing data before inserting.

    Args:
        db: Async SQLAlchemy session
    """
    logger.info("Starting database seeding...")

    # ── Seed Roles ───────────────────────────────────────────────
    existing_roles = await db.execute(select(Role))
    if not existing_roles.scalars().first():
        for role_data in ROLES:
            role = Role(name=role_data["name"], description=role_data["description"])
            db.add(role)
        await db.flush()
        logger.info(f"Seeded {len(ROLES)} roles")
    else:
        logger.info("Roles already exist, skipping seed")

    # ── Seed Demo Tenant ─────────────────────────────────────────
    existing_tenant = await db.execute(select(Tenant).where(Tenant.department_code == DEMO_TENANT["department_code"]))
    tenant = existing_tenant.scalars().first()
    if not tenant:
        tenant = Tenant(name=DEMO_TENANT["name"], department_code=DEMO_TENANT["department_code"])
        db.add(tenant)
        await db.flush()
        logger.info(f"Seeded demo tenant: {DEMO_TENANT['name']}")
    else:
        logger.info("Demo tenant already exists, skipping seed")

    # ── Seed Demo Users ──────────────────────────────────────────
    hashed_pw = pwd_context.hash(DEMO_PASSWORD)
    user_map = {}  # email → user object

    for user_data in DEMO_USERS:
        existing_user = await db.execute(select(User).where(User.email == user_data["email"]))
        user = existing_user.scalars().first()
        if not user:
            role_result = await db.execute(select(Role).where(Role.name == user_data["role_name"]))
            role = role_result.scalars().first()
            user = User(
                email=user_data["email"],
                hashed_password=hashed_pw,
                full_name=user_data["full_name"],
                role_id=role.id,
                tenant_id=tenant.id,
                is_active=True,
            )
            db.add(user)
            await db.flush()
            logger.info(f"Seeded user: {user_data['email']} ({user_data['role_name']})")
        user_map[user_data["email"]] = user

    # ── Seed Demo Documents ──────────────────────────────────────
    from app.documents.models import Document

    existing_docs = await db.execute(select(Document))
    if not existing_docs.scalars().first():
        # Load embedding model for document chunks
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info(f"Loaded embedding model for seeding: {settings.EMBEDDING_MODEL}")
        except Exception as e:
            logger.warning(f"Could not load embedding model for seeding: {e}. Seeding documents without embeddings.")
            model = None

        patient_user = user_map.get("patient.001@hospital.com")

        for doc_data in DEMO_DOCUMENTS:
            creator = user_map.get(doc_data["user_email"])
            if not creator:
                logger.warning(f"Creator not found for document: {doc_data['title']}")
                continue

            authorized_roles = doc_data.get("authorized_roles_override", get_roles_for_doc_type(doc_data["doc_type"]))
            is_patient_owned = doc_data.get("is_patient_owned", False)
            owner_id = patient_user.id if (is_patient_owned and patient_user) else None

            doc_id = uuid.uuid4()

            await db.execute(
                sa_text("""
                    INSERT INTO documents (id, tenant_id, title, doc_type, sensitivity_tier,
                        authorized_roles, owner_patient_id, source_filename, created_by)
                    VALUES (:id, :tenant_id, :title, :doc_type, :sensitivity_tier,
                        :authorized_roles, :owner_patient_id, :source_filename, :created_by)
                """),
                {
                    "id": str(doc_id),
                    "tenant_id": str(tenant.id),
                    "title": doc_data["title"],
                    "doc_type": doc_data["doc_type"],
                    "sensitivity_tier": doc_data["sensitivity_tier"],
                    "authorized_roles": authorized_roles,
                    "owner_patient_id": str(owner_id) if owner_id else None,
                    "source_filename": f"{doc_data['title'].lower().replace(' ', '_')}.txt",
                    "created_by": str(creator.id),
                },
            )

            # Create a single chunk per demo document (or split if content is large)
            content = doc_data["content"]
            chunks_text = [content] if len(content) <= settings.CHUNK_SIZE else _simple_chunk(content)

            for idx, chunk_text in enumerate(chunks_text):
                chunk_id = uuid.uuid4()

                if model:
                    embedding = model.encode(chunk_text).tolist()
                    embedding_str = str(embedding)
                    await db.execute(
                        sa_text("""
                            INSERT INTO document_chunks (id, document_id, tenant_id, chunk_index,
                                chunk_text, embedding, authorized_roles, owner_patient_id)
                            VALUES (:id, :document_id, :tenant_id, :chunk_index,
                                :chunk_text, CAST(:embedding AS vector), :authorized_roles, :owner_patient_id)
                        """),
                        {
                            "id": str(chunk_id),
                            "document_id": str(doc_id),
                            "tenant_id": str(tenant.id),
                            "chunk_index": idx,
                            "chunk_text": chunk_text,
                            "embedding": embedding_str,
                            "authorized_roles": authorized_roles,
                            "owner_patient_id": str(owner_id) if owner_id else None,
                        },
                    )
                else:
                    # Insert without embedding
                    await db.execute(
                        sa_text("""
                            INSERT INTO document_chunks (id, document_id, tenant_id, chunk_index,
                                chunk_text, authorized_roles, owner_patient_id)
                            VALUES (:id, :document_id, :tenant_id, :chunk_index,
                                :chunk_text, :authorized_roles, :owner_patient_id)
                        """),
                        {
                            "id": str(chunk_id),
                            "document_id": str(doc_id),
                            "tenant_id": str(tenant.id),
                            "chunk_index": idx,
                            "chunk_text": chunk_text,
                            "authorized_roles": authorized_roles,
                            "owner_patient_id": str(owner_id) if owner_id else None,
                        },
                    )

            logger.info(f"Seeded document: {doc_data['title']} ({len(chunks_text)} chunks)")

        await db.commit()
        logger.info(f"Seeded {len(DEMO_DOCUMENTS)} demo documents")
    else:
        logger.info("Documents already exist, skipping seed")

    logger.info("Database seeding completed!")


def _simple_chunk(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """Simple text chunker for seed data."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks if chunks else [text]


async def main():
    """Run seed script standalone."""
    logging.basicConfig(level=logging.INFO)
    async with AsyncSessionLocal() as db:
        await seed_initial_data(db)


if __name__ == "__main__":
    asyncio.run(main())
