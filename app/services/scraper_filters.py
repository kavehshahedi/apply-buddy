from linkedin_jobs_scraper.filters import (
    BenefitsFilters,
    CommitmentsFilters,
    ExperienceLevelFilters,
    IndustryFilters,
    JobFunctionFilters,
    OnSiteOrRemoteFilters,
    RelevanceFilters,
    SalaryBaseFilters,
    TimeFilters,
    TypeFilters,
)

time_filter_map = {
    "day": TimeFilters.DAY,
    "week": TimeFilters.WEEK,
    "month": TimeFilters.MONTH,
    "any": TimeFilters.ANY,
}

relevance_map = {
    "recent": RelevanceFilters.RECENT,
    "relevant": RelevanceFilters.RELEVANT,
}

type_filter_map = {
    "full_time": TypeFilters.FULL_TIME,
    "part_time": TypeFilters.PART_TIME,
    "contract": TypeFilters.CONTRACT,
    "temporary": TypeFilters.TEMPORARY,
    "internship": TypeFilters.INTERNSHIP,
}

experience_map = {
    "internship": ExperienceLevelFilters.INTERNSHIP,
    "entry": ExperienceLevelFilters.ENTRY_LEVEL,
    "associate": ExperienceLevelFilters.ASSOCIATE,
    "mid_senior": ExperienceLevelFilters.MID_SENIOR,
    "director": ExperienceLevelFilters.DIRECTOR,
    "executive": ExperienceLevelFilters.EXECUTIVE,
}

remote_map = {
    "on_site": OnSiteOrRemoteFilters.ON_SITE,
    "remote": OnSiteOrRemoteFilters.REMOTE,
    "hybrid": OnSiteOrRemoteFilters.HYBRID,
}

industry_map = {
    "airlines_aviation": IndustryFilters.AIRLINES_AVIATION,
    "banking": IndustryFilters.BANKING,
    "civil_engineering": IndustryFilters.CIVIL_ENGINEERING,
    "computer_games": IndustryFilters.COMPUTER_GAMES,
    "environmental_services": IndustryFilters.ENVIRONMENTAL_SERVICES,
    "electronic_manufacturing": IndustryFilters.ELECTRONIC_MANUFACTURING,
    "financial_services": IndustryFilters.FINANCIAL_SERVICES,
    "information_services": IndustryFilters.INFORMATION_SERVICES,
    "investment_banking": IndustryFilters.INVESTMENT_BANKING,
    "investment_management": IndustryFilters.INVESTMENT_MANAGEMENT,
    "it_services": IndustryFilters.IT_SERVICES,
    "legal_services": IndustryFilters.LEGAL_SERVICES,
    "motor_vehicles": IndustryFilters.MOTOR_VEHICLES,
    "oil_gas": IndustryFilters.OIL_GAS,
    "software_development": IndustryFilters.SOFTWARE_DEVELOPMENT,
    "staffing_recruiting": IndustryFilters.STAFFING_RECRUITING,
    "technology_internet": IndustryFilters.TECHNOLOGY_INTERNET,
}

salary_map = {
    "40k": SalaryBaseFilters.SALARY_40K,
    "60k": SalaryBaseFilters.SALARY_60K,
    "80k": SalaryBaseFilters.SALARY_80K,
    "100k": SalaryBaseFilters.SALARY_100K,
    "120k": SalaryBaseFilters.SALARY_120K,
    "140k": SalaryBaseFilters.SALARY_140K,
    "160k": SalaryBaseFilters.SALARY_160K,
    "180k": SalaryBaseFilters.SALARY_180K,
    "200k": SalaryBaseFilters.SALARY_200K,
}

job_function_map = {
    "accounting_auditing": JobFunctionFilters.ACCOUNTING_AUDITING,
    "administrative": JobFunctionFilters.ADMINISTRATIVE,
    "advertising": JobFunctionFilters.ADVERTISING,
    "business_development": JobFunctionFilters.BUSINESS_DEVELOPMENT,
    "consulting": JobFunctionFilters.CONSULTING,
    "distribution": JobFunctionFilters.DISTRIBUTION,
    "design": JobFunctionFilters.DESIGN,
    "education": JobFunctionFilters.EDUCATION,
    "engineering": JobFunctionFilters.ENGINEERING,
    "finance": JobFunctionFilters.FINANCE,
    "general_business": JobFunctionFilters.GENERAL_BUSINESS,
    "health_care_provider": JobFunctionFilters.HEALTH_CARE_PROVIDER,
    "human_resources": JobFunctionFilters.HUMAN_RESOURCES,
    "information_technology": JobFunctionFilters.INFORMATION_TECHNOLOGY,
    "legal": JobFunctionFilters.LEGAL,
    "management": JobFunctionFilters.MANAGEMENT,
    "manufacturing": JobFunctionFilters.MANUFACTURING,
    "marketing": JobFunctionFilters.MARKETING,
    "other": JobFunctionFilters.OTHER,
    "public_relations": JobFunctionFilters.PUBLIC_RELATIONS,
    "product_management": JobFunctionFilters.PRODUCT_MANAGEMENT,
    "project_management": JobFunctionFilters.PROJECT_MANAGEMENT,
    "quality_assurance": JobFunctionFilters.QUALITY_ASSURANCE,
    "research": JobFunctionFilters.RESEARCH,
    "sales": JobFunctionFilters.SALES,
    "supply_chain": JobFunctionFilters.SUPPLY_CHAIN,
    "training": JobFunctionFilters.TRAINING,
}

benefits_map = {
    "medical": BenefitsFilters.MEDICAL,
    "vision": BenefitsFilters.VISION,
    "dental": BenefitsFilters.DENTAL,
    "retirement_401k": BenefitsFilters.RETIREMENT_401K,
    "pension_plan": BenefitsFilters.PENSION_PLAN,
    "paid_maternity_leave": BenefitsFilters.PAID_MATERNITY_LEAVE,
    "paid_paternity_leave": BenefitsFilters.PAID_PATERNITY_LEAVE,
    "commuter_benefits": BenefitsFilters.COMMUTER_BENEFITS,
    "student_loan_assistance": BenefitsFilters.STUDENT_LOAN_ASSISTANCE,
    "tuition_assistance": BenefitsFilters.TUITION_ASSISTANCE,
    "disability_insurance": BenefitsFilters.DISABILITY_INSURANCE,
}

commitments_map = {
    "diversity_equity_inclusion": CommitmentsFilters.DIVERSITY_EQUITY_INCLUSION,
    "environmental_sustainability": CommitmentsFilters.ENVIRONMENTAL_SUSTAINABILITY,
    "work_life_balance": CommitmentsFilters.WORK_LIFE_BALANCE,
    "social_impact": CommitmentsFilters.SOCIAL_IMPACT,
    "career_growth_and_learning": CommitmentsFilters.CAREER_GROWTH_AND_LEARNING,
}
