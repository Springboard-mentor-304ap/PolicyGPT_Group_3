"""
Seed the database with realistic Indian government policies and schemes.
Run: source .venv/bin/activate && python backend/seed_realistic_data.py
"""
import os
import sys
# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date, datetime
from backend.app.db.database import SessionLocal
from backend.app.models.policy import Policy, PolicyCategory, PolicyStatus
from backend.app.models.scheme import Scheme, SchemeCategory, SchemeStatus
from backend.app.models.eligibility_rule import (
    EligibilityRule,
    EligibilityParameter,
    EligibilityOperator,
)
from backend.app.models.user import User

# Fixed UUIDs
GOV_USER_ID = "ccdfbab9-0247-434f-9d61-f27120eaad6a"  # govofficial@m2test.com
ADMIN_USER_ID = "39a99b6f-a8f2-4c26-976b-2f5cc4f6475e"  # admin@policygpt.gov

import uuid


def uid():
    return uuid.uuid4()


db = SessionLocal()

# ── Step 1: Delete all existing policies and schemes ────────────────────────
print("Deleting existing policies and schemes...")
db.query(Scheme).delete()
db.query(Policy).delete()
db.commit()

# ── Step 2: Create realistic policies ───────────────────────────────────────
policies_data = [
    {
        "title": "National Education Policy 2020",
        "description": "A comprehensive reform of the Indian education system aiming to overhaul and restructure the existing educational framework. The policy introduces a 5+3+3+4 curricular structure, emphasizes foundational literacy and numeracy, promotes multilingual education, and integrates technology into classroom learning. It targets universal access to quality education from preschool through higher education.",
        "category": PolicyCategory.EDUCATION,
        "department": "Department of School Education & Literacy",
        "ministry": "Ministry of Education",
        "state": None,
        "status": PolicyStatus.APPROVED,
        "document_url": "https://www.education.gov.in/sites/upload_files/mhrd/files/NEP_Final_English.pdf",
        "published_date": date(2020, 7, 29),
        "required_documents": ["Aadhaar Card", "School Enrollment Proof"],
        "view_count": 1245,
    },
    {
        "title": "Ayushman Bharat — National Health Protection Scheme",
        "description": "India's flagship public health insurance scheme providing coverage of up to ₹5 lakh per family per year for secondary and tertiary hospitalisation. The scheme targets approximately 50 crore beneficiaries from economically vulnerable families, covering over 1,900 medical packages including surgery, medical, and day-care procedures at empanelled public and private hospitals.",
        "category": PolicyCategory.HEALTHCARE,
        "department": "Department of Health & Family Welfare",
        "ministry": "Ministry of Health and Family Welfare",
        "state": None,
        "status": PolicyStatus.APPROVED,
        "document_url": "https://www.pmjay.gov.in/",
        "published_date": date(2018, 9, 23),
        "required_documents": ["Aadhaar Card", "Ration Card", "Income Certificate"],
        "view_count": 892,
    },
    {
        "title": "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)",
        "description": "Direct income support scheme providing ₹6,000 per year to small and marginal farmer families, paid in three equal instalments of ₹2,000. The scheme aims to supplement the financial needs of farmers for procuring various inputs related to agriculture and allied activities, as well as domestic needs. Over 11 crore farmer families have benefited since inception.",
        "category": PolicyCategory.AGRICULTURE,
        "department": "Department of Agriculture & Farmers Welfare",
        "ministry": "Ministry of Agriculture & Farmers Welfare",
        "state": None,
        "status": PolicyStatus.APPROVED,
        "document_url": "https://pmkisan.gov.in/",
        "published_date": date(2019, 2, 24),
        "required_documents": ["Aadhaar Card", "Bank Account Details", "Land Records"],
        "view_count": 2100,
    },
    {
        "title": "Digital India Act — Data Protection Framework",
        "description": "A comprehensive legislative framework governing the processing of personal data by government agencies and private entities. The policy establishes the Digital India Data Protection Authority, mandates data localisation for critical personal data, introduces consent-based data processing, and provides citizens with rights including access, correction, erasure, and data portability.",
        "category": PolicyCategory.DIGITAL_GOVERNANCE,
        "department": "Ministry of Electronics & IT",
        "ministry": "Ministry of Electronics and Information Technology",
        "state": None,
        "status": PolicyStatus.APPROVED,
        "document_url": "https://www.meity.gov.in/data-protection-framework",
        "published_date": date(2023, 8, 11),
        "required_documents": ["Aadhaar Card", "PAN Card"],
        "view_count": 678,
    },
    {
        "title": "National Rural Employment Guarantee Act (MGNREGA)",
        "description": "The world's largest public works programme guaranteeing 100 days of wage employment per year to every rural household whose adult members volunteer for unskilled manual work. The scheme focuses on water conservation, drought proofing, land development, flood control, and rural connectivity. It serves as a critical social safety net for over 6 crore households annually.",
        "category": PolicyCategory.EMPLOYMENT,
        "department": "Ministry of Rural Development",
        "ministry": "Ministry of Rural Development",
        "state": None,
        "status": PolicyStatus.APPROVED,
        "document_url": "https://nrega.nic.in/",
        "published_date": date(2005, 2, 2),
        "required_documents": ["Job Card", "Aadhaar Card", "Bank Account"],
        "view_count": 1567,
    },
    {
        "title": "PM Awas Yojana — Urban Housing for All",
        "description": "A mission to provide all-weather pucca houses with basic amenities to all eligible urban households by 2024. The scheme provides central assistance of ₹1.50 lakh for Economically Weaker Sections (EWS) and ₹1 lakh for Low Income Groups (LIG) through credit-linked subsidies. Beneficiaries include urban poor living in slums, street vendors, and rickshaw pullers.",
        "category": PolicyCategory.HOUSING,
        "department": "Ministry of Housing and Urban Affairs",
        "ministry": "Ministry of Housing and Urban Affairs",
        "state": None,
        "status": PolicyStatus.APPROVED,
        "document_url": "https://pmaymis.gov.in/",
        "published_date": date(2015, 6, 25),
        "required_documents": ["Aadhaar Card", "Income Certificate", "Land Documents", "BPL Certificate"],
        "view_count": 934,
    },
    {
        "title": "National Green Hydrogen Mission",
        "description": "A strategic initiative to position India as a global hub for green hydrogen production and export. The mission targets production capacity of 5 million metric tonnes per annum by 2030, with an outlay of ₹19,744 crore. It covers electrolyser manufacturing, green hydrogen production in identified zones, and development of infrastructure for storage, transportation, and distribution.",
        "category": PolicyCategory.ENVIRONMENT,
        "department": "Ministry of New and Renewable Energy",
        "ministry": "Ministry of New and Renewable Energy",
        "state": None,
        "status": PolicyStatus.APPROVED,
        "document_url": "https://mnre.gov.in/green-hydrogen",
        "published_date": date(2024, 1, 4),
        "required_documents": ["Company Registration", "Environmental Clearance", "Land Lease Agreement"],
        "view_count": 456,
    },
    {
        "title": "Stand-Up India Scheme for SC/ST and Women Entrepreneurs",
        "description": "Facilitates bank loans between ₹10 lakh and ₹1 crore for setting up greenfield enterprises in manufacturing, services, or trading sectors. Targeted at at least one SC/ST borrower and at least one woman borrower per bank branch. The scheme includes a composite loan covering term loan and working capital, with a repayment period of up to 7 years.",
        "category": PolicyCategory.FINANCE,
        "department": "Department of Financial Services",
        "ministry": "Ministry of Finance",
        "state": None,
        "status": PolicyStatus.APPROVED,
        "document_url": "https://www.standupindia.gov.in/",
        "published_date": date(2016, 4, 5),
        "required_documents": ["Aadhaar Card", "Caste Certificate (for SC/ST)", "Business Plan", "Educational Qualification"],
        "view_count": 345,
    },
    {
        "title": "Beti Bachao Beti Padhao",
        "description": "A tri-ministerial programme addressing declining child sex ratio and promoting education of the girl child. The scheme operates across 640 districts with convergence of health, education, and women development interventions. It includes awareness campaigns, enforcement of PC-PNDT Act, and recognition of schools with excellent enrollment of girls.",
        "category": PolicyCategory.WOMEN_CHILD_WELFARE,
        "department": "Ministry of Women and Child Development",
        "ministry": "Ministry of Women and Child Development",
        "state": None,
        "status": PolicyStatus.APPROVED,
        "document_url": "https://betibachao.nic.in/",
        "published_date": date(2015, 1, 22),
        "required_documents": ["Birth Certificate of Girl Child", "Aadhaar Card", "School Enrollment Proof"],
        "view_count": 678,
    },
    {
        "title": "Bharatmala Pariyojana — National Highway Development",
        "description": "India's largest highway development programme envisaging construction of 34,800 km of national highways at an estimated cost of ₹5.35 lakh crore. The programme includes economic corridors, inter-corridor and feeder routes, national corridor efficiency improvements, border and coastal connectivity roads, and green-field expressways with advanced traffic management systems.",
        "category": PolicyCategory.INFRASTRUCTURE,
        "department": "Ministry of Road Transport & Highways",
        "ministry": "Ministry of Road Transport and Highways",
        "state": None,
        "status": PolicyStatus.APPROVED,
        "document_url": "https://bharatmala.nic.in/",
        "published_date": date(2017, 10, 31),
        "required_documents": ["Land Acquisition Documents", "Environmental Clearance"],
        "view_count": 543,
    },
    {
        "title": "PM eVIDYA — Unified Digital Education Platform",
        "description": "A comprehensive initiative to digitise and deliver quality education through multiple modes — DIKSHA portal, Swayam Prabha TV channels, SWAYAM online courses, and community radio. The platform provides 200+ SWAYAM Prabha DTH channels, 340 MOOCs, and accessible content for differently-abled students in Indian Sign Language.",
        "category": PolicyCategory.EDUCATION,
        "department": "Department of Higher Education",
        "ministry": "Ministry of Education",
        "state": None,
        "status": PolicyStatus.PENDING_APPROVAL,
        "document_url": "https://diksha.gov.in/",
        "published_date": date(2024, 5, 15),
        "required_documents": ["Student ID", "School Affiliation Letter"],
        "view_count": 123,
    },
    {
        "title": "Smart Cities Mission — Urban Infrastructure Modernisation",
        "description": "Aims to develop 100 smart cities with advanced infrastructure, sustainable environments, and technology-driven solutions. The mission focuses on area-based development including retrofitting, redevelopment, green-field development, and pan-city smart solutions. Core components include integrated command and control centres, intelligent transport systems, and smart water management.",
        "category": PolicyCategory.INFRASTRUCTURE,
        "department": "Ministry of Housing and Urban Affairs",
        "ministry": "Ministry of Housing and Urban Affairs",
        "state": None,
        "status": PolicyStatus.REJECTED,
        "rejection_reason": "The proposal lacks a clear budget allocation and implementation timeline. Please revise with detailed financial projections and district-level action plans.",
        "document_url": "https://smartcities.gov.in/",
        "published_date": date(2024, 3, 10),
        "required_documents": ["City Development Plan", "Smart Infrastructure Blueprint"],
        "view_count": 89,
    },
]

policies = []
for pd in policies_data:
    p = Policy(
        id=uid(),
        title=pd["title"],
        description=pd["description"],
        category=pd["category"],
        department=pd["department"],
        ministry=pd["ministry"],
        state=pd["state"],
        status=pd["status"],
        document_url=pd.get("document_url"),
        published_date=pd.get("published_date"),
        required_documents=pd.get("required_documents"),
        uploaded_by=GOV_USER_ID,
        approved_by=ADMIN_USER_ID if pd["status"] == PolicyStatus.APPROVED else None,
        rejection_reason=pd.get("rejection_reason"),
        view_count=pd.get("view_count", 0),
    )
    db.add(p)
    policies.append(p)
    print(f"  ✓ Policy: {p.title} ({p.status.value})")

db.flush()  # Get IDs

# ── Step 3: Create realistic schemes linked to policies ─────────────────────
schemes_data = [
    {
        "policy_index": 0,  # NEP 2020
        "title": "PM SHRI Schools — Quality Education Initiative",
        "description": "Upgrading 14,500 existing schools into model institutions implementing NEP 2020. Schools receive smart classrooms, labs, libraries, sports facilities, and ICT infrastructure. Focus on holistic development, experiential learning, and competency-based assessment with reduced board exam stress.",
        "category": SchemeCategory.STUDENT_SCHEMES,
        "benefits": ["Smart classroom setup", "ICT infrastructure worth ₹25 lakh per school", "Teacher training programmes", "Free textbooks for EWS students", "Sports equipment grants"],
        "required_documents": ["School UDISE Code", "NEP Readiness Assessment", "Headmaster Recommendation"],
        "application_process": "Schools apply through the State Education Department. Selection is based on NEP readiness assessment and infrastructure gap analysis.",
        "department": "Department of School Education",
        "state": None,
        "status": SchemeStatus.ACTIVE,
        "launch_date": date(2022, 9, 7),
        "deadline_date": date(2025, 12, 31),
        "document_url": "https://pmshri.education.gov.in/",
        "view_count": 890,
    },
    {
        "policy_index": 1,  # Ayushman Bharat
        "title": "Ayushman Bharat Health Account (ABHA)",
        "description": "Digital health identity for every citizen enabling secure, paperless access to health records across the National Digital Health Ecosystem. ABHA number links all health records — prescriptions, lab reports, discharge summaries — accessible through a consent-based framework at any empanelled hospital.",
        "category": SchemeCategory.HEALTHCARE,
        "benefits": ["Free digital health ID", "Unified health records across hospitals", "Cashless treatment at empanelled hospitals", "Up to ₹5 lakh coverage per family", "Telemedicine access"],
        "required_documents": ["Aadhaar Card", "PAN Card (optional)", "Mobile Number"],
        "application_process": "Register online at abdm.gov.in or through the Ayushman Bharat app. Aadhaar-based eKYC for verification.",
        "department": "National Health Authority",
        "state": None,
        "status": SchemeStatus.ACTIVE,
        "launch_date": date(2021, 9, 27),
        "deadline_date": None,
        "document_url": "https://abdm.gov.in/",
        "view_count": 1567,
    },
    {
        "policy_index": 2,  # PM-KISAN
        "title": "PM-KISAN Maan Dhan Yojana",
        "description": "Pension scheme for small and marginal farmers providing ₹3,000 per month after age 60. The government contributes an equal amount to the pension fund. Farmers aged 18-40 can enrol with a monthly contribution of ₹55 to ₹200 based on age. The scheme provides social security to farmers with no regular pension coverage.",
        "category": SchemeCategory.FARMER_WELFARE,
        "benefits": ["₹3,000 monthly pension after age 60", "Government matches farmer contribution", "50% contribution by Central Government", "Voluntary and contributory pension", "Family pension provision"],
        "required_documents": ["Aadhaar Card", "Bank Account Passbook", "Land Records (Khasra)", "Age Proof"],
        "application_process": "Register at nearest CSC or through Maan Dhan portal. Aadhaar-linked bank account mandatory for contribution auto-debit.",
        "department": "Department of Agriculture & Farmers Welfare",
        "state": None,
        "status": SchemeStatus.ACTIVE,
        "launch_date": date(2019, 9, 12),
        "deadline_date": None,
        "document_url": "https://maandhan.in/",
        "view_count": 2340,
    },
    {
        "policy_index": 4,  # MGNREGA
        "title": "MGNREGA Wage Employment — Current Year",
        "description": "Guaranteed 100 days of unskilled manual wage employment per household per financial year. Daily wage ranges from ₹204 to ₹323 depending on the state. Work includes water harvesting, land development, rural roads, flood control, and drought proofing. Social audit mandatory in every gram panchayat.",
        "category": SchemeCategory.EMPLOYMENT_PROGRAMS,
        "benefits": ["100 days guaranteed employment", "State-level minimum wage payment", "Unemployment allowance if work not provided", "Worksite facilities (crèche, first aid)", "Social audit participation"],
        "required_documents": ["MGNREGA Job Card", "Aadhaar Card", "Bank/Post Office Account"],
        "application_process": "Apply to Gram Panchayat with Aadhaar and bank details. Job card issued within 15 days. Work allocation within 15 days of demand.",
        "department": "Ministry of Rural Development",
        "state": None,
        "status": SchemeStatus.ACTIVE,
        "launch_date": date(2005, 4, 2),
        "deadline_date": None,
        "document_url": "https://nrega.nic.in/",
        "view_count": 3456,
    },
    {
        "policy_index": 5,  # PM Awas
        "title": "PM Awas Yojana — Credit Linked Subsidy Scheme (CLSS)",
        "description": "Interest subsidy of 3% to 6.5% on home loans for EWS/LIG/MIG categories. EWS families (annual income up to ₹3 lakh) receive 6.5% subsidy on loans up to ₹6 lakh. The scheme operates through primary lending institutions including banks and housing finance companies.",
        "category": SchemeCategory.HOUSING,
        "benefits": ["Up to 6.5% interest subsidy", "Loan tenure up to 20 years", "Subsidy on principal outstanding", "Extended to middle income groups", "No upper limit on loan amount"],
        "required_documents": ["Aadhaar Card", "Income Certificate", "Property Documents", "Bank Statements (6 months)", "Employment Proof"],
        "application_process": "Apply through any Primary Lending Institution (PLI) — bank or housing finance company. Submit documents for income verification and property appraisal.",
        "department": "Ministry of Housing and Urban Affairs",
        "state": None,
        "status": SchemeStatus.ACTIVE,
        "launch_date": date(2017, 6, 1),
        "deadline_date": date(2025, 3, 31),
        "document_url": "https://pmaymis.gov.in/",
        "view_count": 1234,
    },
    {
        "policy_index": 7,  # Stand-Up India
        "title": "MUDRA Yojana — Micro Units Development & Refinance",
        "description": "Provides loans up to ₹10 lakh to non-corporate, non-farm small/micro enterprises. Three categories: Shishu (up to ₹50,000), Kishore (₹50,001 to ₹5 lakh), and Tarun (₹5,00,001 to ₹10 lakh). No collateral required. Available through banks, NBFCs, and MFIs.",
        "category": SchemeCategory.BUSINESS_SUPPORT,
        "benefits": ["Loans up to ₹10 lakh without collateral", "Three categories based on business stage", "No processing fee for Shishu loans", "Repayment tenure up to 5 years", "Across 1.5 lakh lending points"],
        "required_documents": ["Aadhaar Card", "PAN Card", "Business Plan / Project Report", "Caste Certificate (for Stand-Up India)", "Voter ID / Passport"],
        "application_process": "Apply online at mudra.org.in or visit nearest bank branch. Shishu loans disbursed within 7 days. KYC and basic document verification.",
        "department": "Department of Financial Services",
        "ministry": "Ministry of Finance",
        "state": None,
        "status": SchemeStatus.ACTIVE,
        "launch_date": date(2015, 4, 8),
        "deadline_date": None,
        "document_url": "https://www.mudra.org.in/",
        "view_count": 4567,
    },
    {
        "policy_index": 8,  # Beti Bachao Beti Padhao
        "title": "Sukanya Samriddhi Yojana — Girl Child Prosperity",
        "description": "Small deposit savings scheme for girl children below 10 years offering 8.2% annual interest (highest among small savings schemes). Maximum deposit ₹1.5 lakh per year for 15 years. Maturity amount received after 21 years or at marriage after 18. Tax-free returns under Section 80C.",
        "category": SchemeCategory.WOMEN_EMPOWERMENT,
        "benefits": ["8.2% annual interest rate", "Tax-free maturity amount", "Deposit limit ₹1.5 lakh/year", "Partial withdrawal at 18 for education", "Maturity in 21 years"],
        "required_documents": ["Girl Child Birth Certificate", "Parent/Guardian Aadhaar Card", "Address Proof", "Bank/Payment Slip"],
        "application_process": "Open account at any post office or authorised commercial bank branch. Minimum initial deposit ₹250. One account per girl child.",
        "department": "Ministry of Women and Child Development",
        "state": None,
        "status": SchemeStatus.ACTIVE,
        "launch_date": date(2015, 1, 22),
        "deadline_date": None,
        "document_url": "https://www.indiapost.gov.in/VAS/Pages/SSY.aspx",
        "view_count": 2890,
    },
    {
        "policy_index": 6,  # Green Hydrogen
        "title": "Green Hydrogen Pilot Projects — Funding Initiative",
        "description": "Funding support for setting up green hydrogen production facilities at strategic locations. Provides capital subsidy of up to 30% of project cost for first 10 pilot projects. Targets electrolyser capacity of 500 MW by 2025 in Gujarat, Maharashtra, and Tamil Nadu industrial corridors.",
        "category": SchemeCategory.SOCIAL_SECURITY,
        "benefits": ["30% capital subsidy on project cost", "Land allocation in industrial zones", "Power purchase agreements at subsidised rates", "Technical assistance from NTPC/IOC", "Export facilitation support"],
        "required_documents": ["Company Registration Certificate", "Environmental Clearance", "Project Feasibility Report", "Land Lease Agreement", "Financial Statements"],
        "application_process": "Submit proposal to MNRE through the National Green Hydrogen Mission portal. Evaluation by expert committee based on technical feasibility and financial viability.",
        "department": "Ministry of New and Renewable Energy",
        "state": "Gujarat",
        "status": SchemeStatus.ACTIVE,
        "launch_date": date(2024, 2, 1),
        "deadline_date": date(2025, 6, 30),
        "document_url": "https://mnre.gov.in/green-hydrogen-pilot",
        "view_count": 234,
    },
    {
        "policy_index": 3,  # Digital India
        "title": "DigiLocker — Digital Document Wallet",
        "description": "Government-issued digital document wallet providing secure cloud storage for all verified documents. Citizens can store, access, and share Aadhaar, PAN, driving licence, vehicle RC, academic certificates, and 500+ document types. Documents in DigiLocker carry the same legal validity as originals under the IT Act.",
        "category": SchemeCategory.STUDENT_SCHEMES,
        "benefits": ["1 GB free cloud storage", "Legally valid digital documents", "Auto-fetch from issuing agencies", "QR code verification", "Share documents directly with authorities"],
        "required_documents": ["Aadhaar Card (linked mobile number)"],
        "application_process": "Download DigiLocker app or visit digilocker.gov.in. Register with Aadhaar and OTP verification. Documents auto-fetched from connected government databases.",
        "department": "Ministry of Electronics & IT",
        "state": None,
        "status": SchemeStatus.ACTIVE,
        "launch_date": date(2015, 7, 1),
        "deadline_date": None,
        "document_url": "https://digilocker.gov.in/",
        "view_count": 5678,
    },
    {
        "policy_index": 9,  # Bharatmala
        "title": "Expressway Development Programme — Phase I",
        "description": "Construction of 26 greenfield expressways connecting major economic hubs. Includes the Delhi-Mumbai Expressway (1,350 km), Bengaluru-Chennai Expressway, and Amritsar-Jamnagar Economic Corridor. Features controlled-access highways with toll plazas, rest areas, and highway patrol.",
        "category": SchemeCategory.SOCIAL_SECURITY,
        "benefits": ["Reduced travel time by 40%", "35,000+ jobs during construction", "Logistics cost reduction of 15%", "Improved road safety standards", "Connectivity to ports and airports"],
        "required_documents": ["Land Acquisition Documents", "Environmental Clearance", "Traffic Survey Report"],
        "application_process": "Tenders issued through NHAI portal. EPC contracts awarded through competitive bidding. Land acquisition handled by state governments.",
        "department": "National Highways Authority of India",
        "state": None,
        "status": SchemeStatus.ACTIVE,
        "launch_date": date(2023, 1, 15),
        "deadline_date": date(2027, 12, 31),
        "document_url": "https://nhai.gov.in/",
        "view_count": 678,
    },
]

for sd in schemes_data:
    parent_policy = policies[sd["policy_index"]]
    s = Scheme(
        id=uid(),
        policy_id=parent_policy.id,
        title=sd["title"],
        description=sd["description"],
        category=sd["category"],
        benefits=sd.get("benefits"),
        required_documents=sd.get("required_documents"),
        application_process=sd.get("application_process"),
        department=sd.get("department"),
        state=sd.get("state"),
        status=sd["status"],
        launch_date=sd.get("launch_date"),
        deadline_date=sd.get("deadline_date"),
        document_url=sd.get("document_url"),
        created_by=GOV_USER_ID,
        approved_by=ADMIN_USER_ID if sd["status"] == SchemeStatus.ACTIVE else None,
        view_count=sd.get("view_count", 0),
    )
    db.add(s)
    print(f"  ✓ Scheme: {s.title} ({s.status.value})")

db.flush()

# ── Step 4: Create eligibility rules ──────────────────────────────────────────
eligibility_rules = {
    "PM SHRI Schools — Quality Education Initiative": [
        (EligibilityParameter.AGE, EligibilityOperator.GTE, "6"),
        (EligibilityParameter.EDUCATION, EligibilityOperator.EQ, "school"),
    ],
    "Ayushman Bharat Health Account (ABHA)": [
        (EligibilityParameter.AGE, EligibilityOperator.GTE, "0"),
        (EligibilityParameter.INCOME, EligibilityOperator.LTE, "800000"),
    ],
    "PM-KISAN Maan Dhan Yojana": [
        (EligibilityParameter.AGE, EligibilityOperator.GTE, "18"),
        (EligibilityParameter.AGE, EligibilityOperator.LTE, "40"),
        (EligibilityParameter.OCCUPATION, EligibilityOperator.EQ, "farmer"),
    ],
    "MGNREGA Wage Employment — Current Year": [
        (EligibilityParameter.AGE, EligibilityOperator.GTE, "18"),
        (EligibilityParameter.OCCUPATION, EligibilityOperator.EQ, "unskilled_worker"),
    ],
    "PM Awas Yojana — Credit Linked Subsidy Scheme (CLSS)": [
        (EligibilityParameter.INCOME, EligibilityOperator.LTE, "300000"),
        (EligibilityParameter.STATE, EligibilityOperator.EQ, "Karnataka"),
    ],
    "MUDRA Yojana — Micro Units Development & Refinance": [
        (EligibilityParameter.AGE, EligibilityOperator.GTE, "18"),
        (EligibilityParameter.OCCUPATION, EligibilityOperator.EQ, "self-employed"),
    ],
    "Sukanya Samriddhi Yojana — Girl Child Prosperity": [
        (EligibilityParameter.AGE, EligibilityOperator.LTE, "10"),
        (EligibilityParameter.GENDER, EligibilityOperator.EQ, "female"),
    ],
    "Green Hydrogen Pilot Projects — Funding Initiative": [
        (EligibilityParameter.STATE, EligibilityOperator.EQ, "Gujarat"),
        (EligibilityParameter.OCCUPATION, EligibilityOperator.EQ, "business"),
    ],
    "DigiLocker — Digital Document Wallet": [
        (EligibilityParameter.AGE, EligibilityOperator.GTE, "0"),
    ],
    "Expressway Development Programme — Phase I": [
        (EligibilityParameter.AGE, EligibilityOperator.GTE, "18"),
        (EligibilityParameter.EDUCATION, EligibilityOperator.EQ, "graduate"),
    ],
}

scheme_by_title = {
    scheme.title: scheme
    for scheme in db.query(Scheme).all()
}

rule_count = 0

for scheme_title, rules in eligibility_rules.items():
    scheme = scheme_by_title.get(scheme_title)

    if not scheme:
        print(f"  ⚠ Scheme not found for eligibility rules: {scheme_title}")
        continue

    for parameter, operator, value in rules:
        rule = EligibilityRule(
            id=uid(),
            scheme_id=scheme.id,
            parameter=parameter,
            operator=operator,
            value=value,
        )
        db.add(rule)
        rule_count += 1

    print(f"  ✓ Eligibility rules: {scheme.title} ({len(rules)})")
db.commit()

print(
    f"\n✅ Done! Created {len(policies)} policies, "
    f"{len(schemes_data)} schemes, and {rule_count} eligibility rules."
)
db.close()
