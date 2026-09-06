import pandas as pd
import random

parent_companies = [
    "BEST ELECTRONICS", "MEENA BAZAR", "AARONG", "BURGER KING",
    "STEP FOOTWEAR", "BAY EMPORIUM", "AGORA LIMITED", "DAILY SHOPPING",
    "GLORIA JEAN'S COFFEES", "BATA SHOE"
]

child_prefixes = [
    "Banani", "Gulshan", "Dhanmondi", "Uttara", "Mirpur",
    "Chittagong", "Sylhet", "Rajshahi", "Khulna", "Barishal",
    "Narsingdi", "Gazipur", "Narayanganj", "Comilla", "Bogura",
    "Rangpur", "Dinajpur", "Mymensingh", "Faridpur", "Jessore"
]

pra_names = [
    "BROTHERS MEDICINE CENTER", "AL MADINA STORE", "RAHMAN TELECOM",
    "KARIM PHARMACY", "HOSSAIN ELECTRONICS", "ISLAM GENERAL STORE",
    "AHMED MOBILE BANKING", "AKTER COSMETICS", "KHAN TRADERS",
    "BEGUM ENTERPRISE", "MOLLA MEDICAL HALL", "SALAM TELECOM",
    "NOOR PHARMACY", "HABIB STORE", "REZA ELECTRONICS",
    "JANNAT AGENCY", "MASUM TRADERS", "BILLAH STORE",
    "SUMON TELECOM", "LIMON COSMETIC"
]

kam_names = [
    "Sifaul Islam", "Didarul Islam", "Ishrak Alam", "Rashedul Islam", "Shahriar Hossain", "Nasrin Akter", "Kamrul Hossain", "Sumaiya Islam", "Nargis Akter", "Jannatul Ferdous", "Mostofa Ahmed",
    "Shamima Sultana"
]

divisions = ["Dhaka", "Chittagong", "Sylhet", "Rajshahi", "Khulna", "Barishal", "Rangpur", "Mymensingh"]

agents = []


for i in range(500):
    company = parent_companies[i % len(parent_companies)]
    wallet  = f"17{random.randint(10000000, 99999999)}"
    if i < 350:
        status = "Active"
    elif i < 45:
        status = "Pending"
    else:
        status = "Rejected"

    agents.append({
        "Parent/Child":    "Parent",
        "Wallet No.":      wallet,
        "DBA":             company,
        "Parent Merchant": company,
        "Status":          status,
        "KAM":             random.choice(kam_names),
        "Division":        random.choice(divisions),
        "Merchant ID":     f"112{random.randint(1000000000000, 9999999999999)}",
        "Email":           f"info@{company.lower().replace(' ', '')}.com",
        "Merchant Type":   "Corporate",
        "Persona":         "Regular"
    })


for i in range(1000):
    company = parent_companies[i % len(parent_companies)]
    branch  = child_prefixes[i % len(child_prefixes)]
    wallet  = f"18{random.randint(10000000, 99999999)}"
    if i < 450:
        status = "Active"
    elif i < 370:
        status = "Pending"
    else:
        status = "Rejected"

    agents.append({
        "Parent/Child":    "Child",
        "Wallet No.":      wallet,
        "DBA":             f"{company}-{branch}",
        "Parent Merchant": company,
        "Status":          status,
        "KAM":             random.choice(kam_names),
        "Division":        random.choice(divisions),
        "Merchant ID":     f"112{random.randint(1000000000000, 9999999999999)}",
        "Email":           f"{branch.lower()}@{company.lower().replace(' ', '')}.com",
        "Merchant Type":   "Corporate",
        "Persona":         "Regular"
    })

for i in range(500):
    name   = pra_names[i % len(pra_names)]
    wallet = f"01{random.randint(700000000, 999999999)}"
    if i < 320:
        status = "Active"
    elif i < 45:
        status = "Pending"
    else:
        status = "Rejected"

    agents.append({
        "Parent/Child":    "PRA",
        "Wallet No.":      wallet,
        "DBA":             name,
        "Parent Merchant": "",
        "Status":          status,
        "KAM":             random.choice(kam_names),
        "Division":        random.choice(divisions),
        "Merchant ID":     f"112{random.randint(1000000000000, 9999999999999)}",
        "Email":           f"info@{name.lower().replace(' ', '')}.com",
        "Merchant Type":   "Individual",
        "Persona":         "Regular"
    })

random.shuffle(agents)

df = pd.DataFrame(agents)
df.to_excel("agents.xlsx", index=False)
print(f"Created agents.xlsx with {len(agents)} agents")
print(df["Parent/Child"].value_counts())
print(df["Status"].value_counts())