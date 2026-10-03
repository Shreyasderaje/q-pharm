"""Build the Q-Pharm data artifacts.

  * drug_library.json  — curated FDA-approved/late-stage drugs with PubChem-resolved,
                         RDKit-validated SMILES + metadata (class, indication,
                         documented repurposing history)
  * ml_model.json      — logistic-regression drug-likeness model trained on
                         library (positives) vs curated non-drug chemicals (negatives)
  * targets.json       — curated screening targets, verified live against RCSB
  * evidence.json      — curated literature links per target

Run:  python scripts/build_data.py   (from backend/, with the venv active)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import rdMolDescriptors  # noqa: E402

RDLogger.DisableLog("rdApp.*")

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/{prop}/JSON"

# --------------------------------------------------------------------------- #
# Curated drug metadata
# (name = PubChem-searchable, db = DrugBank ID when confidently known)
# --------------------------------------------------------------------------- #

R = {"to": "...", "note": "..."}  # placeholder hint only

DRUGS = [
    # --- analgesics / NSAIDs ---
    ("Aspirin", "DB00945", "NSAID", "Pain, fever, antiplatelet", {"to": "Colorectal cancer prevention", "note": "Long-term low-dose aspirin reduces CRC incidence; classic repurposing case."}),
    ("Paracetamol", "DB00316", "Analgesic", "Pain, fever", None),
    ("Ibuprofen", "DB01050", "NSAID", "Pain, inflammation", None),
    ("Naproxen", "DB00560", "NSAID", "Pain, arthritis", None),
    ("Diclofenac", "DB00586", "NSAID", "Pain, arthritis", None),
    ("Aceclofenac", None, "NSAID", "Osteoarthritis pain", None),
    ("Nimesulide", None, "NSAID", "Pain, inflammation", None),
    ("Celecoxib", "DB00382", "COX-2 inhibitor", "Arthritis, pain", {"to": "Familial adenomatous polyposis", "note": "COX-2 inhibition approved to reduce polyps in FAP."}),
    ("Indomethacin", "DB00328", "NSAID", "Arthritis, gout", None),
    ("Meloxicam", "DB00814", "NSAID", "Osteoarthritis", None),
    ("Ketoprofen", "DB01009", "NSAID", "Pain, inflammation", None),
    ("Ketorolac", "DB00465", "NSAID", "Acute pain", None),
    ("Piroxicam", "DB00542", "NSAID", "Arthritis", None),
    ("Sulindac", "DB00605", "NSAID", "Arthritis", None),
    # --- opioids ---
    ("Tramadol", "DB00193", "Opioid analgesic", "Moderate pain", None),
    ("Morphine", "DB00295", "Opioid analgesic", "Severe pain", None),
    ("Codeine", "DB00318", "Opioid analgesic", "Cough, mild pain", None),
    ("Fentanyl", "DB00813", "Opioid analgesic", "Severe pain", None),
    ("Oxycodone", "DB00497", "Opioid analgesic", "Severe pain", None),
    ("Methadone", "DB00333", "Opioid agonist", "Opioid dependence, pain", None),
    ("Buprenorphine", "DB00921", "Partial opioid agonist", "Opioid dependence, pain", None),
    ("Naloxone", "DB01183", "Opioid antagonist", "Opioid overdose", None),
    ("Naltrexone", "DB00704", "Opioid antagonist", "Alcohol/opioid dependence", None),
    # --- cardiovascular ---
    ("Atorvastatin", "DB01076", "Statin", "Hyperlipidemia", None),
    ("Simvastatin", "DB00641", "Statin", "Hyperlipidemia", None),
    ("Rosuvastatin", None, "Statin", "Hyperlipidemia", None),
    ("Pravastatin", None, "Statin", "Hyperlipidemia", None),
    ("Ezetimibe", None, "Cholesterol absorption inhibitor", "Hyperlipidemia", None),
    ("Fenofibrate", None, "Fibrate", "Dyslipidemia", None),
    ("Gemfibrozil", None, "Fibrate", "Dyslipidemia", None),
    ("Losartan", "DB00678", "ARB", "Hypertension", None),
    ("Valsartan", "DB00177", "ARB", "Hypertension, heart failure", None),
    ("Telmisartan", None, "ARB", "Hypertension", None),
    ("Irbesartan", None, "ARB", "Hypertension", None),
    ("Candesartan", None, "ARB", "Hypertension", None),
    ("Enalapril", "DB00584", "ACE inhibitor", "Hypertension, heart failure", None),
    ("Ramipril", "DB00775", "ACE inhibitor", "Hypertension", None),
    ("Captopril", "DB00786", "ACE inhibitor", "Hypertension", None),
    ("Lisinopril", "DB00722", "ACE inhibitor", "Hypertension", None),
    ("Amlodipine", "DB00381", "Calcium channel blocker", "Hypertension, angina", None),
    ("Nifedipine", "DB01115", "Calcium channel blocker", "Angina, hypertension", None),
    ("Diltiazem", "DB00343", "Calcium channel blocker", "Angina, hypertension", None),
    ("Verapamil", "DB00661", "Calcium channel blocker", "Angina, arrhythmia", None),
    ("Metoprolol", "DB00264", "Beta blocker", "Hypertension, MI", None),
    ("Propranolol", "DB00571", "Beta blocker", "Hypertension, anxiety, migraine", None),
    ("Atenolol", "DB00335", "Beta blocker", "Hypertension", None),
    ("Carvedilol", "DB00612", "Beta blocker", "Heart failure", None),
    ("Bisoprolol", None, "Beta blocker", "Hypertension, heart failure", None),
    ("Sotalol", None, "Beta blocker / antiarrhythmic", "Arrhythmia", None),
    ("Amiodarone", "DB01118", "Antiarrhythmic", "Arrhythmia", None),
    ("Digoxin", "DB00390", "Cardiac glycoside", "Heart failure, AF", None),
    ("Flecainide", "DB01195", "Antiarrhythmic", "Arrhythmia", None),
    ("Furosemide", "DB00695", "Loop diuretic", "Edema, heart failure", None),
    ("Hydrochlorothiazide", "DB00999", "Thiazide diuretic", "Hypertension", None),
    ("Chlorthalidone", None, "Thiazide diuretic", "Hypertension", None),
    ("Spironolactone", "DB00421", "Aldosterone antagonist", "Heart failure, hypertension", None),
    ("Eplerenone", None, "Aldosterone antagonist", "Heart failure", None),
    ("Acetazolamide", "DB00819", "Carbonic anhydrase inhibitor", "Glaucoma, altitude sickness", None),
    ("Mannitol", None, "Osmotic diuretic", "Raised intracranial pressure", None),
    ("Nitroglycerin", None, "Nitrate", "Angina", None),
    ("Isosorbide dinitrate", None, "Nitrate", "Angina", None),
    ("Warfarin", "DB00482", "Anticoagulant", "Thrombosis, AF", None),
    ("Apixaban", None, "Factor Xa inhibitor", "Thrombosis, AF", None),
    ("Rivaroxaban", None, "Factor Xa inhibitor", "Thrombosis", None),
    ("Dabigatran", None, "Thrombin inhibitor", "Thrombosis, AF", None),
    ("Clopidogrel", "DB00758", "Antiplatelet", "Atherosclerotic events", None),
    ("Colchicine", "DB01111", "Anti-gout", "Gout, FMF", {"to": "Cardiovascular events", "note": "LoDoCo2/Colcot trials established low-dose colchicine for atheroprotection."}),
    ("Allopurinol", "DB00437", "Xanthine oxidase inhibitor", "Gout", None),
    ("Febuxostat", None, "Xanthine oxidase inhibitor", "Gout", None),
    ("Sildenafil", "DB00203", "PDE5 inhibitor", "Erectile dysfunction, PAH", {"to": "Erectile dysfunction / PAH", "note": "Developed for angina; the PDE5 side effect became the indication."}),
    ("Tadalafil", "DB00810", "PDE5 inhibitor", "ED, BPH, PAH", None),
    ("Minoxidil", "DB00350", "Vasodilator", "Severe hypertension", {"to": "Alopecia", "note": "Antihypertensive whose hypertrichosis side effect became topical hair-loss therapy."}),
    ("Finasteride", "DB00623", "5-alpha reductase inhibitor", "BPH", {"to": "Male-pattern alopecia", "note": "BPH drug repurposed at lower dose for hair loss."}),
    ("Dutasteride", None, "5-alpha reductase inhibitor", "BPH", None),
    # --- CNS ---
    ("Fluoxetine", "DB00472", "SSRI", "Depression, OCD", None),
    ("Sertraline", "DB01104", "SSRI", "Depression, anxiety", None),
    ("Paroxetine", "DB00715", "SSRI", "Depression, anxiety", None),
    ("Citalopram", "DB00215", "SSRI", "Depression", None),
    ("Escitalopram", "DB01175", "SSRI", "Depression, anxiety", None),
    ("Venlafaxine", "DB00205", "SNRI", "Depression, anxiety", None),
    ("Duloxetine", "DB00476", "SNRI", "Depression, neuropathic pain", {"to": "Stress urinary incontinence / fibromyalgia", "note": "SNRI extended across pain and urology indications."}),
    ("Bupropion", "DB01156", "NDRI", "Depression", {"to": "Smoking cessation", "note": "Antidepressant repurposed as the first non-nicotine smoking-cessation drug."}),
    ("Mirtazapine", "DB00370", "NaSSA", "Depression", None),
    ("Trazodone", "DB00650", "SARI", "Depression, insomnia", None),
    ("Buspirone", "DB00247", "5-HT1A agonist", "Anxiety", None),
    ("Clozapine", "DB00363", "Atypical antipsychotic", "Treatment-resistant schizophrenia", None),
    ("Olanzapine", "DB00334", "Atypical antipsychotic", "Schizophrenia, bipolar", None),
    ("Quetiapine", "DB01224", "Atypical antipsychotic", "Schizophrenia, bipolar", None),
    ("Risperidone", "DB00734", "Atypical antipsychotic", "Schizophrenia, bipolar", None),
    ("Aripiprazole", "DB01238", "Partial dopamine agonist", "Schizophrenia, bipolar", None),
    ("Haloperidol", "DB00502", "Typical antipsychotic", "Psychosis", None),
    ("Donepezil", "DB00843", "Acetylcholinesterase inhibitor", "Alzheimer's disease", None),
    ("Memantine", "DB01043", "NMDA antagonist", "Alzheimer's disease", None),
    ("Rivastigmine", "DB00989", "Cholinesterase inhibitor", "Dementia", None),
    ("Levodopa", "DB01235", "Dopamine precursor", "Parkinson's disease", None),
    ("Carbidopa", "DB00190", "DOPA decarboxylase inhibitor", "Parkinson's (adjunct)", None),
    ("Pramipexole", "DB00413", "Dopamine agonist", "Parkinson's disease", None),
    ("Ropinirole", "DB00278", "Dopamine agonist", "Parkinson's disease", None),
    ("Selegiline", "DB01037", "MAO-B inhibitor", "Parkinson's disease", None),
    ("Entacapone", "DB00494", "COMT inhibitor", "Parkinson's (adjunct)", None),
    ("Amantadine", "DB00916", "Antiviral", "Influenza A", {"to": "Parkinson's disease", "note": "Antiviral whose dopaminergic effects were repurposed for parkinsonism."}),
    ("Riluzole", "DB00752", "Glutamate modulator", "ALS", None),
    ("Sumatriptan", "DB00915", "Triptan", "Migraine", None),
    ("Rizatriptan", None, "Triptan", "Migraine", None),
    ("Gabapentin", "DB00996", "Gabapentinoid", "Neuropathic pain, epilepsy", None),
    ("Pregabalin", "DB00230", "Gabapentinoid", "Neuropathic pain, fibromyalgia", None),
    ("Carbamazepine", "DB00564", "Anticonvulsant", "Epilepsy, trigeminal neuralgia", None),
    ("Phenytoin", "DB00252", "Anticonvulsant", "Epilepsy", None),
    ("Valproic acid", "DB00313", "Anticonvulsant", "Epilepsy, bipolar", None),
    ("Lamotrigine", "DB00555", "Anticonvulsant", "Epilepsy, bipolar", None),
    ("Levetiracetam", "DB01202", "Anticonvulsant", "Epilepsy", None),
    ("Topiramate", "DB00273", "Anticonvulsant", "Epilepsy, migraine", None),
    ("Diazepam", "DB00842", "Benzodiazepine", "Anxiety, seizures", None),
    ("Lorazepam", "DB00186", "Benzodiazepine", "Anxiety, status epilepticus", None),
    ("Alprazolam", "DB00404", "Benzodiazepine", "Anxiety, panic", None),
    ("Zolpidem", "DB00425", "Hypnotic", "Insomnia", None),
    ("Ketamine", None, "Anesthetic", "Anesthesia", {"to": "Treatment-resistant depression", "note": "Anesthetic repurposed as rapid-acting antidepressant (esketamine approved)."}),
    # --- diabetes / endocrine ---
    ("Metformin", "DB00331", "Biguanide", "Type 2 diabetes", {"to": "Cancer / aging (trials)", "note": "AMPK activation sparked broad repurposing trials (TAME, oncology)."}),
    ("Glipizide", "DB01067", "Sulfonylurea", "Type 2 diabetes", None),
    ("Glibenclamide", None, "Sulfonylurea", "Type 2 diabetes", None),
    ("Glimepiride", None, "Sulfonylurea", "Type 2 diabetes", None),
    ("Pioglitazone", "DB01132", "PPAR-gamma agonist", "Type 2 diabetes", None),
    ("Rosiglitazone", None, "PPAR-gamma agonist", "Type 2 diabetes (restricted)", None),
    ("Acarbose", "DB00204", "Alpha-glucosidase inhibitor", "Type 2 diabetes", None),
    ("Sitagliptin", "DB01121", "DPP-4 inhibitor", "Type 2 diabetes", None),
    ("Saxagliptin", None, "DPP-4 inhibitor", "Type 2 diabetes", None),
    ("Empagliflozin", None, "SGLT2 inhibitor", "Type 2 diabetes, HF", None),
    ("Dapagliflozin", None, "SGLT2 inhibitor", "Diabetes, HF, CKD", None),
    ("Canagliflozin", None, "SGLT2 inhibitor", "Type 2 diabetes", None),
    ("Levothyroxine", None, "Thyroid hormone", "Hypothyroidism", None),
    ("Methimazole", None, "Antithyroid", "Hyperthyroidism", None),
    ("Propylthiouracil", None, "Antithyroid", "Hyperthyroidism", None),
    # --- respiratory / allergy ---
    ("Albuterol", "DB01001", "Beta-2 agonist", "Asthma, COPD", None),
    ("Ipratropium", "DB00332", "Antimuscarinic", "COPD, asthma", None),
    ("Tiotropium", None, "Antimuscarinic", "COPD", None),
    ("Montelukast", "DB00471", "Leukotriene antagonist", "Asthma, allergy", None),
    ("Zafirlukast", None, "Leukotriene antagonist", "Asthma", None),
    ("Theophylline", "DB00277", "Methylxanthine", "Asthma, COPD", None),
    ("Budesonide", "DB01222", "Corticosteroid", "Asthma, Crohn's", None),
    ("Fluticasone propionate", None, "Corticosteroid", "Asthma, rhinitis", None),
    # --- GI ---
    ("Omeprazole", "DB00338", "PPI", "GERD, ulcers", None),
    ("Esomeprazole", "DB00767", "PPI", "GERD", None),
    ("Lansoprazole", None, "PPI", "GERD", None),
    ("Pantoprazole", None, "PPI", "GERD", None),
    ("Rabeprazole", None, "PPI", "GERD", None),
    ("Famotidine", "DB00927", "H2 blocker", "GERD, ulcers", None),
    ("Ranitidine", "DB00863", "H2 blocker", "GERD (withdrawn)", None),
    ("Ondansetron", "DB00904", "5-HT3 antagonist", "Nausea/vomiting", None),
    ("Metoclopramide", "DB00912", "Prokinetic", "Gastroparesis", None),
    ("Domperidone", None, "Prokinetic", "Gastroparesis (ex-US)", None),
    ("Loperamide", None, "Antidiarrheal", "Diarrhea", None),
    ("Mesalamine", "DB00543", "Aminosalicylate", "Ulcerative colitis", None),
    ("Sulfasalazine", "DB00552", "Aminosalicylate", "UC, rheumatoid arthritis", None),
    ("Ursodeoxycholic acid", None, "Bile acid", "Primary biliary cholangitis, gallstones", None),
    # --- anti-infectives: antibacterial ---
    ("Amoxicillin", "DB01060", "Beta-lactam", "Bacterial infections", None),
    ("Cephalexin", None, "Beta-lactam (cephalosporin)", "Bacterial infections", None),
    ("Ceftriaxone", "DB01212", "Cephalosporin", "Bacterial infections", None),
    ("Meropenem", "DB00760", "Carbapenem", "Severe bacterial infections", None),
    ("Aztreonam", None, "Monobactam", "Gram-negative infections", None),
    ("Azithromycin", "DB00207", "Macrolide", "Bacterial infections", {"to": "COVID-19 / inflammation (trials)", "note": "Immunomodulatory macrolide widely triaged in 2020."}),
    ("Clarithromycin", "DB01211", "Macrolide", "Bacterial infections", None),
    ("Erythromycin", None, "Macrolide", "Bacterial infections", None),
    ("Clindamycin", None, "Lincosamide", "Anaerobic/Gram+ infections", None),
    ("Doxycycline", "DB00254", "Tetracycline", "Broad infections, malaria prophylaxis", {"to": "Rosacea / periodontitis", "note": "Sub-antimicrobial anti-inflammatory dosing repurposed."}),
    ("Minocycline", None, "Tetracycline", "Acne, infections", {"to": "Neuroinflammation (trials)", "note": "Anti-inflammatory tetracycline trialed in neurodegeneration and stroke."}),
    ("Tigecycline", None, "Glycylcycline", "Complicated infections", None),
    ("Gentamicin", "DB00798", "Aminoglycoside", "Gram-negative infections", None),
    ("Amikacin", None, "Aminoglycoside", "Resistant Gram-negatives", None),
    ("Vancomycin", "DB00513", "Glycopeptide", "MRSA", None),
    ("Daptomycin", None, "Lipopeptide", "Gram+ resistant infections", None),
    ("Linezolid", None, "Oxazolidinone", "MRSA, VRE", None),
    ("Nitrofurantoin", None, "Nitrofuran", "UTI", None),
    ("Ciprofloxacin", "DB00537", "Fluoroquinolone", "UTI, broad infections", None),
    ("Levofloxacin", None, "Fluoroquinolone", "Pneumonia, UTI", None),
    ("Moxifloxacin", None, "Fluoroquinolone", "Pneumonia", None),
    ("Ofloxacin", None, "Fluoroquinolone", "UTI", None),
    ("Metronidazole", None, "Nitroimidazole", "Anaerobes, protozoa", None),
    ("Tinidazole", None, "Nitroimidazole", "Protozoa, anaerobes", None),
    ("Rifampicin", None, "Rifamycin", "Tuberculosis", None),
    ("Isoniazid", None, "Anti-TB", "Tuberculosis", None),
    ("Pyrazinamide", None, "Anti-TB", "Tuberculosis", None),
    ("Ethambutol", None, "Anti-TB", "Tuberculosis", None),
    ("Bedaquiline", None, "ATP synthase inhibitor", "MDR tuberculosis", None),
    ("Clofazimine", None, "Rimino-phenazine", "Leprosy", {"to": "Gram-negative pneumonia / cancer (trials)", "note": "Leprosy drug repurposed against M. abscessus and explored in oncology."}),
    ("Dapsone", None, "Sulfone", "Leprosy, dermatitis herpetiformis", None),
    ("Levamisole", None, "Anthelmintic / immunomodulator", "Ascariasis", {"to": "Colorectal cancer (historical adjuvant)", "note": "Anthelmintic repurposed as immunoadjuvant in CRC."}),
    # --- antifungal / antiparasitic ---
    ("Fluconazole", "DB00196", "Azole antifungal", "Candidiasis, cryptococcosis", None),
    ("Ketoconazole", "DB01026", "Azole antifungal", "Dermatomycoses, Cushing's", None),
    ("Itraconazole", "DB01167", "Azole antifungal", "Histoplasmosis, aspergillosis", {"to": "Cancer (trials)", "note": "Antifungal with Hedgehog-pathway and anti-angiogenic activity."}),
    ("Voriconazole", "DB01240", "Azole antifungal", "Invasive aspergillosis", None),
    ("Posaconazole", None, "Azole antifungal", "Prophylaxis in neutropenia", None),
    ("Terbinafine", "DB00857", "Allylamine", "Onychomycosis, tinea", None),
    ("Griseofulvin", "DB00400", "Antifungal", "Dermatophytosis", None),
    ("Amphotericin B", "DB00681", "Polyene antifungal", "Systemic mycoses", None),
    ("Chloroquine", "DB00608", "4-aminoquinoline", "Malaria", {"to": "Lupus / rheumatoid arthritis", "note": "Antimalarial backbone of autoimmune therapy; 2020 COVID studies."}),
    ("Hydroxychloroquine", "DB01611", "4-aminoquinoline", "Malaria, lupus, RA", {"to": "Autoimmune disease", "note": "Antimalarial repurposed as staple immunomodulator; COVID-19 trials."}),
    ("Primaquine", "DB01089", "8-aminoquinoline", "Relapse malaria", None),
    ("Pyrimethamine", None, "DHFR inhibitor", "Malaria, toxoplasmosis", None),
    ("Sulfadoxine", None, "Sulfonamide", "Malaria (combination)", None),
    ("Mefloquine", "DB00358", "Quinoline", "Malaria prophylaxis", None),
    ("Artemether", None, "Artemisinin derivative", "Malaria", {"to": "Cancer (trials)", "note": "Antimalarial endoperoxides explored as anticancer agents."}),
    ("Lumefantrine", None, "Aryl amino alcohol", "Malaria (combination)", None),
    ("Artesunate", None, "Artemisinin derivative", "Severe malaria", None),
    ("Atovaquone", None, "Hydroxynaphthoquinone", "Malaria prophylaxis, PJP", None),
    ("Proguanil", None, "Biguanide", "Malaria prophylaxis", None),
    ("Quinine", "DB00468", "Alkaloid", "Malaria", None),
    ("Ivermectin", "DB00602", "Macrocyclic lactone", "Onchocerciasis, strongyloidiasis", {"to": "Scabies / lymphatic filariasis", "note": "Veterinary antiparasitic repositioned for human NTDs (Nobel 2015)."}),
    ("Albendazole", "DB00518", "Benzimidazole", "Helminthiasis", None),
    ("Mebendazole", "DB00642", "Benzimidazole", "Helminthiasis", {"to": "Cancer (trials)", "note": "Tubulin-binding anthelmintic explored in oncology."}),
    ("Praziquantel", None, "Anthelmintic", "Schistosomiasis, tapeworm", None),
    ("Diethylcarbamazine", None, "Anthelmintic", "Lymphatic filariasis", None),
    ("Nitazoxanide", None, "Thiazolide", "Cryptosporidiosis, giardiasis", {"to": "Antiviral / oncology (trials)", "note": "Broad-spectrum repurposing candidate (influenza, HCV, CRC)."}),
    ("Niclosamide", None, "Salicylanilide", "Tapeworm", {"to": "Cancer / antiviral (trials)", "note": "Anthelmintic with broad pathway inhibition; top repurposing candidate."}),
    ("Miltefosine", None, "Phosphocholine analog", "Leishmaniasis", {"to": "Leishmaniasis", "note": "Originally investigated as anticancer agent; became first oral leishmaniasis drug."}),
    ("Auranofin", None, "Gold compound", "Rheumatoid arthritis", {"to": "Amoebiasis / oncology (trials)", "note": "Thioredoxin-reductase inhibition repurposed against parasites and cancer."}),
    ("Suramin", None, "Naphthylurea", "Sleeping sickness, onchocerciasis", None),
    ("Eflornithine", None, "Ornithine decarboxylase inhibitor", "Sleeping sickness; hirsutism (topical)", None),
    ("Pentamidine", None, "Aromatic diamidine", "PJP, trypanosomiasis", None),
    ("Nifurtimox", None, "Nitrofuran", "Chagas disease", None),
    ("Benznidazole", None, "Nitroimidazole", "Chagas disease", None),
    ("Ebselen", None, "Organoselenium", "Investigational (stroke, hearing loss; approved in Japan)", {"to": "SARS-CoV-2 Mpro inhibitor", "note": "Top computational hit for Mpro inhibition in 2020 screens."}),
    # --- antivirals ---
    ("Remdesivir", "DB14761", "Nucleotide analog", "Ebola (developed); COVID-19", {"to": "COVID-19", "note": "Ebola asset repositioned to first authorized SARS-CoV-2 therapy (RdRp)."}),
    ("Nirmatrelvir", None, "Protease inhibitor", "COVID-19", None),
    ("Molnupiravir", None, "Nucleoside analog", "COVID-19 (EUA)", None),
    ("Favipiravir", "DB12466", "RdRp inhibitor", "Influenza (Japan)", {"to": "COVID-19 / NTDs (trials)", "note": "Broad-spectrum RNA-virus polymerase inhibitor."}),
    ("Umifenovir", "DB13627", "Fusion inhibitor", "Influenza (RU/CN)", {"to": "COVID-19 (trials)", "note": "Membrane-fusion inhibitor trialed against SARS-CoV-2."}),
    ("Oseltamivir", "DB00585", "Neuraminidase inhibitor", "Influenza", None),
    ("Zanamivir", None, "Neuraminidase inhibitor", "Influenza", None),
    ("Baloxavir marboxil", None, "Cap-dependent endonuclease inhibitor", "Influenza", None),
    ("Acyclovir", "DB00787", "Nucleoside analog", "Herpesviruses", None),
    ("Valacyclovir", None, "Nucleoside analog prodrug", "Herpesviruses", None),
    ("Ganciclovir", "DB01004", "Nucleoside analog", "CMV", None),
    ("Zidovudine", "DB00495", "NRTI", "HIV-1", {"to": "HIV/AIDS", "note": "Failed cancer compound became the first approved AIDS drug."}),
    ("Lamivudine", "DB00709", "NRTI", "HIV-1, HBV", None),
    ("Emtricitabine", None, "NRTI", "HIV-1", None),
    ("Tenofovir", None, "Nucleotide analog", "HIV-1, HBV", None),
    ("Efavirenz", "DB00625", "NNRTI", "HIV-1", None),
    ("Nevirapine", "DB00238", "NNRTI", "HIV-1", None),
    ("Raltegravir", None, "Integrase inhibitor", "HIV-1", None),
    ("Dolutegravir", None, "Integrase inhibitor", "HIV-1", None),
    ("Ritonavir", "DB00503", "Protease inhibitor", "HIV-1 (booster)", None),
    ("Lopinavir", "DB01601", "Protease inhibitor", "HIV-1", {"to": "COVID-19 (trials)", "note": "Kaletra trialed against SARS-CoV-2 proteases."}),
    ("Darunavir", "DB06795", "Protease inhibitor", "HIV-1", None),
    ("Atazanavir", "DB01072", "Protease inhibitor", "HIV-1", None),
    ("Sofosbuvir", "DB08934", "NS5B inhibitor", "Hepatitis C", None),
    ("Simeprevir", None, "NS3/4A inhibitor", "Hepatitis C", None),
    ("Boceprevir", "DB08870", "NS3/4A inhibitor", "Hepatitis C", {"to": "SARS-CoV-2 Mpro (studies)", "note": "HCV protease inhibitor shown to inhibit SARS-CoV-2 Mpro."}),
    ("Telaprevir", None, "NS3/4A inhibitor", "Hepatitis C", None),
    ("Ribavirin", "DB00811", "Guanosine analog", "HCV, RSV, Lassa", {"to": "HCV / viral hemorrhagic fevers", "note": "Broad-spectrum antiviral repeatedly repositioned."}),
    ("Entecavir", "DB00452", "Nucleoside analog", "Hepatitis B", None),
    # --- oncology / immunology ---
    ("Methotrexate", "DB00563", "Antifolate", "Cancer, RA, psoriasis", None),
    ("Azathioprine", "DB00993", "Purine antimetabolite", "Transplant, autoimmune", None),
    ("Mercaptopurine", None, "Purine antimetabolite", "ALL", None),
    ("Hydroxycarbamide", None, "Ribonucleotide reductase inhibitor", "CML, sickle cell", None),
    ("Cyclophosphamide", "DB00531", "Alkylating agent", "Cancer, vasculitis", None),
    ("Ifosfamide", None, "Alkylating agent", "Sarcoma", None),
    ("Etoposide", None, "Topoisomerase II inhibitor", "Lymphoma, lung cancer", None),
    ("Doxorubicin", None, "Anthracycline", "Broad cancer", None),
    ("Paclitaxel", None, "Taxane", "Broad cancer", None),
    ("Docetaxel", None, "Taxane", "Broad cancer", None),
    ("Vincristine", None, "Vinca alkaloid", "Leukemia, lymphoma", None),
    ("Vinblastine", None, "Vinca alkaloid", "Lymphoma", None),
    ("Fluorouracil", None, "Antimetabolite", "CRC, skin cancer", None),
    ("Capecitabine", None, "Prodrug of 5-FU", "CRC, breast", None),
    ("Gemcitabine", None, "Antimetabolite", "Pancreatic, lung", None),
    ("Cisplatin", None, "Platinum agent", "Testicular, ovarian, lung", None),
    ("Cyclosporine", "DB01091", "Calcineurin inhibitor", "Transplant, psoriasis", None),
    ("Tacrolimus", "DB00864", "Calcineurin inhibitor", "Transplant, atopic dermatitis", None),
    ("Sirolimus", "DB00877", "mTOR inhibitor", "Transplant", {"to": "Lymphangioleiomyomatosis", "note": "mTOR inhibition repurposed for LAM and coated stents."}),
    ("Everolimus", "DB01590", "mTOR inhibitor", "Transplant, cancer", None),
    ("Imatinib", "DB00619", "BCR-ABL inhibitor", "CML, GIST", None),
    ("Dasatinib", "DB01254", "BCR-ABL/Src inhibitor", "CML", None),
    ("Erlotinib", "DB01197", "EGFR inhibitor", "NSCLC, pancreatic", None),
    ("Gefitinib", "DB00317", "EGFR inhibitor", "NSCLC", None),
    ("Sunitinib", "DB01268", "RTK inhibitor", "RCC, GIST", None),
    ("Sorafenib", None, "Multikinase inhibitor", "HCC, RCC", None),
    ("Lapatinib", None, "HER2/EGFR inhibitor", "Breast cancer", None),
    ("Tamoxifen", "DB00675", "SERM", "Breast cancer", {"to": "Bipolar mania (trials)", "note": "PKC inhibition explored for acute mania."}),
    ("Raloxifene", "DB00481", "SERM", "Osteoporosis", None),
    ("Letrozole", "DB01006", "Aromatase inhibitor", "Breast cancer", None),
    ("Anastrozole", "DB01217", "Aromatase inhibitor", "Breast cancer", None),
    ("Fulvestrant", None, "SERD", "Breast cancer", None),
    ("Thalidomide", "DB01041", "Immunomodulator", "Myeloma, ENL", {"to": "Multiple myeloma / leprosy", "note": "Withdrawn teratogen reborn as anti-angiogenic myeloma therapy."}),
    ("Lenalidomide", "DB00880", "Immunomodulator", "Myeloma, MDS", None),
    ("Pomalidomide", None, "Immunomodulator", "Refractory myeloma", None),
    ("Tretinoin", "DB00755", "Retinoid", "APL, acne", None),
    ("Isotretinoin", "DB00982", "Retinoid", "Severe acne", None),
    ("Alendronate", "DB00630", "Bisphosphonate", "Osteoporosis", None),
    ("Zoledronic acid", None, "Bisphosphonate", "Bone metastases, osteoporosis", None),
    ("Calcitriol", None, "Vitamin D analog", "Renal osteodystrophy", None),
    ("Cholecalciferol", None, "Vitamin D3", "Vitamin D deficiency", None),
    # --- misc ---
    ("Dexamethasone", "DB01234", "Corticosteroid", "Inflammation, edema", {"to": "COVID-19 mortality reduction", "note": "RECOVERY trial: first drug shown to cut COVID-19 deaths."}),
    ("Prednisolone", "DB00860", "Corticosteroid", "Inflammation, autoimmune", None),
    ("Prednisone", "DB00635", "Corticosteroid", "Inflammation, autoimmune", None),
]

# Non-drug negative examples for the ML model: industrial chemicals, dyes,
# pesticides, alkylating toxophores, PAINS motifs.
NEGATIVES = [
    "c1ccccc1",                              # benzene
    "Cc1ccccc1",                             # toluene
    "Oc1ccccc1",                             # phenol
    "Nc1ccccc1",                             # aniline
    "ClC(Cl)(Cl)C(Cl)(Cl)Cl",                # hexachloroethane
    "C=CC(=O)H",                             # acrolein
    "C=CC(=O)OC",                            # methyl acrylate
    "Nc1ccccc1N",                            # o-phenylenediamine
    "O=[N+]([O-])c1ccccc1",                  # nitrobenzene
    "c1ccoc1",                               # furan
    "OCCCOc1ccc(Cl)cc1Cl",                   # 2,4-D fragment-like ether
    "COP(=O)(OC)SCC(=O)NC(C)C",             # malathion-like phosphorothioate
    "O=C(OC(C)(C)c1ccccc1)Oc2ccccc2C(C)(C)", # bisphenol-type
    "O=[N+]([O-])OCC(O)COP(=O)(O)OCC[N+](C)(C)C",  # phosphocholine-like
    "CC1=CC(=O)C=CC1=O",                     # emodin-like quinone core
    "Oc1cc(O)cc(O)c1",                       # pyrogallol
    "Oc1ccc(O)c2ccccc12",                    # catechol-naphthol
    "O=C1SC(=S)N(C)C1=O",                    # rhodanine (PAINS)
    "COC(=O)C(C#N)=C1OC=CC1",                # cyano-coumarin-like PAINS
    "O=C(NCc1ccccc1)c1ccccc1O",              # hydroxybenzamide dye-like
    "CN(C)c1ccc(/C=C/C(=O)O)cc1",            # styryl dye
    "O=[N+]([O-])c1ccc(S(=O)(=O)O)cc1",      # sulfonated nitro-aromatic
    "c1ccc(-c2ccccc2)cc1",                   # biphenyl
    "Clc1ccccc1C(Cl)(Cl)Cl",                 # DDT fragment
    "OC(=O)c1ccc(Cl)cc1Cl",                  # 2,4-D
    "O=S(=O)(O)c1ccccc1",                    # benzenesulfonic acid
    "Nc1nc2ccccc2s1",                        # benzothiazolamine
    "C=CCl",                                 # vinyl chloride
    "OCC1OCCC1",                             # dioxane-like
    "ClCCl",                                 # dichloromethane
    "OCC(O)COP(=O)(O)OCC[N+](C)(C)C",        # glycerophosphocholine-like polar
    "O=C(O)c1ccccc1O",                       # salicylic-acid-like industrial
    "CC(=O)Nc1ccc(O)cc1N(=O)=O",             # nitro-paracetamol-like
    "Nc1ccccc1S(=O)(=O)Nc1ccccc1",           # sulfonamide dye-like
    "O=[N+]([O-])Oc1ccc(cc1)C",              # nitro-cresol
    "Cc1cc(C)c(S(=O)(=O)O)cc1",              # xylene sulfonate
    "Clc1ccc(Oc2ccccc2)cc1",                 # ether herbicide-like
    "O=Cc1ccc(O)cc1",                        # hydroxybenzaldehyde
    "OCCc1ccccc1",                           # phenethyl alcohol
    "CSCCCBr",                               # alkyl bromide toxophore
    "O=C1NC(=O)C(c2ccccc2)N1",               # hydantoin reactive-like
    "OCCN(C)CCc1ccccc1OC",                   # basic flexible ether
    "O=[N+]([O-])c1ccc(OCC(O)COP(=O)(O)O)cc1",  # polar nitro-phosphate
    "CC(=C)C(=O)O",                          # methacrylic acid
    "O=C(O)CCc1ccccc1",                      # hydrocinnamic acid
    "OC(=O)c1ccccc1",                        # benzoic acid
    "Oc1ccccc1OCc1ccccc1",                   # phenoxyphenol
    "CSc1ccccc1",                            # thioanisole
    "Nc1ncnc2[nH]cnc12",                     # purine-like polar base
    "O=[N+]([O-])c1cc(ccc1)C(=O)O",          # nitrobenzoic acid
]


# --------------------------------------------------------------------------- #
# PubChem resolution
# --------------------------------------------------------------------------- #

def pubchem_smiles(name: str, session: requests.Session) -> str | None:
    for prop in ("SMILES", "IsomericSMILES", "CanonicalSMILES", "ConnectivitySMILES"):
        try:
            r = session.get(PUBCHEM.format(name=name, prop=prop), timeout=20)
            if r.status_code == 200:
                data = r.json()
                props = data.get("PropertyTable", {}).get("Properties", [{}])[0]
                smi = props.get(prop) or props.get("SMILES") or props.get("IsomericSMILES") or props.get("CanonicalSMILES")
                if smi:
                    return smi
        except Exception:
            pass
        time.sleep(0.15)
    return None


def build_library() -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": "Q-Pharm/1.0 (research build)"})
    library: list[dict] = []
    failed: list[str] = []
    for i, (name, db, cls, indication, repurpose) in enumerate(DRUGS):
        smi = pubchem_smiles(name, session)
        ok = False
        if smi:
            mol = Chem.MolFromSmiles(smi)
            if mol is not None:
                canonical = Chem.MolToSmiles(mol)
                library.append({
                    "id": f"DB-LIB-{i + 1:03d}",
                    "name": name,
                    "drugbank_id": db,
                    "drug_class": cls,
                    "indication": indication,
                    "smiles": canonical,
                    "mw": round(rdMolDescriptors.CalcExactMolWt(mol), 2),
                    "known_repurposing": repurpose,
                })
                ok = True
                print(f"  [{i + 1:3d}/{len(DRUGS)}] {name}: OK ({len(canonical)} chars)")
        if not ok:
            failed.append(name)
            print(f"  [{i + 1:3d}/{len(DRUGS)}] {name}: FAILED")
        time.sleep(0.25)
    with open(DATA_DIR / "drug_library.json", "w", encoding="utf-8") as fh:
        json.dump(library, fh, indent=2)
    print(f"\nLibrary written: {len(library)} drugs ({len(failed)} failed: {failed})")
    return library


# --------------------------------------------------------------------------- #
# ML model training
# --------------------------------------------------------------------------- #

def features_for(mol: Chem.Mol) -> list[float]:
    from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

    mw = Descriptors.MolWt(mol)
    logp = Crippen.MolLogP(mol)
    tpsa = rdMolDescriptors.CalcTPSA(mol)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)
    rotb = Lipinski.NumRotatableBonds(mol)
    arom = rdMolDescriptors.CalcNumAromaticRings(mol)
    fcsp3 = rdMolDescriptors.CalcFractionCSP3(mol)
    heavy = mol.GetNumHeavyAtoms()
    charge = Chem.GetFormalCharge(mol)
    aromatic_atoms = sum(1 for a in mol.GetAtoms() if a.GetIsAromatic())
    ap = aromatic_atoms / max(heavy, 1)
    logs = 0.16 - 0.63 * logp - 0.0062 * mw + 0.066 * rotb - 0.74 * ap
    return [mw, logp, tpsa, hbd, hba, rotb, arom, fcsp3, heavy, charge, logs]


def train_model(library: list[dict]) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.core.ml import DruglikenessModel

    feature_names = ["mw", "logp", "tpsa", "hbd", "hba", "rotb",
                     "aromatic_rings", "fraction_csp3", "heavy_atoms", "formal_charge", "esol_log_s"]

    X, y = [], []
    for d in library:
        mol = Chem.MolFromSmiles(d["smiles"])
        if mol is None:
            continue
        X.append(features_for(mol))
        y.append(1)
    n_pos = len(X)

    neg_mols = []
    for smi in NEGATIVES:
        mol = Chem.MolFromSmiles(smi)
        if mol is not None:
            neg_mols.append(mol)
            X.append(features_for(mol))
            y.append(0)

    rng = np.random.default_rng(42)
    # augment negatives with clipped Gaussian jitter
    base_neg = np.array(X[n_pos:])
    for _ in range(3):
        jitter = base_neg * (1 + rng.normal(0, 0.06, size=base_neg.shape))
        jitter = np.clip(jitter, base_neg * 0.4, base_neg * 1.6)
        for row in jitter:
            X.append(row.tolist())
            y.append(0)

    Xa = np.array(X, dtype=float)
    ya = np.array(y, dtype=float)
    perm = rng.permutation(len(ya))
    model = DruglikenessModel.train(Xa[perm], ya[perm], feature_names)
    with open(DATA_DIR / "ml_model.json", "w", encoding="utf-8") as fh:
        json.dump(model.export(), fh, indent=2)
    print(f"ML model trained: {n_pos} drug positives, {len(ya) - n_pos} negatives")
    # quick sanity check
    checks = {
        "Aspirin-like (drug)": "CC(=O)Oc1ccccc1C(=O)O",
        "Benzene (non-drug)": "c1ccccc1",
        "Metformin (drug)": "CN(C)C(=N)NC(=N)N",
        "Acrolein (non-drug)": "C=CC=O",
    }
    for label, smi in checks.items():
        mol = Chem.MolFromSmiles(smi)
        print(f"    p(drug-like) {label}: {model.predict_proba(dict(zip(feature_names, features_for(mol)))):.3f}")


# --------------------------------------------------------------------------- #
# Curated targets (verified live against RCSB)
# --------------------------------------------------------------------------- #

TARGET_CANDIDATES = [
    {
        "pdb_id": "6LU7", "name": "SARS-CoV-2 Main Protease (Mpro)", "organism": "SARS-CoV-2",
        "disease": "COVID-19", "priority": 1, "pocket_ligand": "PJE",
        "description": "The coronavirus main protease in complex with inhibitor N3 (PJE) — the primary antiviral drug target of COVID-19.",
    },
    {
        "pdb_id": "7BV2", "name": "SARS-CoV-2 RNA-dependent RNA Polymerase (nsp12)", "organism": "SARS-CoV-2",
        "disease": "COVID-19", "priority": 1, "pocket_ligand": "F86",
        "description": "The viral replication enzyme captured with remdesivir monophosphate (F86) at its catalytic site — the canonical repurposing success.",
    },
    {
        "pdb_id": "6M0J", "name": "SARS-CoV-2 Spike RBD bound to ACE2", "organism": "SARS-CoV-2",
        "disease": "COVID-19", "priority": 2, "pocket_ligand": None,
        "description": "Receptor-binding domain of the spike protein at its human ACE2 interface — entry-inhibitor target (geometric pocket).",
    },
    {
        "pdb_id": "1J3I", "name": "Plasmodium falciparum DHFR-TS", "organism": "Plasmodium falciparum",
        "disease": "Malaria", "priority": 2, "pocket_ligand": "WRA",
        "description": "Parasite dihydrofolate reductase in complex with antifolate WR99210 — target of pyrimethamine-class antimalarials.",
    },
    {
        "pdb_id": "2HU4", "name": "Influenza A N1 Neuraminidase", "organism": "Influenza A virus",
        "disease": "Influenza", "priority": 3, "pocket_ligand": "G39",
        "description": "Group-1 N1 neuraminidase with oseltamivir (G39) bound — the enzyme behind the flu drug Tamiflu.",
    },
    {
        "pdb_id": "4EY7", "name": "Human Acetylcholinesterase", "organism": "Homo sapiens",
        "disease": "Alzheimer's disease", "priority": 3, "pocket_ligand": "E20",
        "description": "Human acetylcholinesterase in complex with donepezil (E20) — the cholinergic drug target.",
    },
    {
        "pdb_id": "1HVR", "name": "HIV-1 Protease", "organism": "HIV-1",
        "disease": "HIV/AIDS", "priority": 3, "pocket_ligand": "XK2",
        "description": "The aspartyl protease behind HAART therapy, with inhibitor XK2 — a classic antiviral docking benchmark.",
    },
    {
        "pdb_id": "4M9K", "name": "Dengue Virus NS2B-NS3 Protease", "organism": "Dengue virus",
        "disease": "Dengue", "priority": 2, "pocket_ligand": None,
        "description": "The flaviviral two-component protease essential for dengue replication — no approved direct inhibitor exists (geometric pocket).",
    },
    {
        "pdb_id": "5LC0", "name": "Zika Virus NS3 Helicase", "organism": "Zika virus",
        "disease": "Zika fever", "priority": 3, "pocket_ligand": "6T8",
        "description": "Zika NS3 helicase with an ATP-site inhibitor (6T8) — a conserved flaviviral replication motor.",
    },
    {
        "pdb_id": "1OHR", "name": "Human Hsp90", "organism": "Homo sapiens",
        "disease": "Cancer (chaperone)", "priority": 3, "pocket_ligand": "1UN",
        "description": "Molecular chaperone Hsp90 in complex with a resorcinol inhibitor (1UN) — oncology target.",
    },
]


def build_targets() -> None:
    from app.core.pdb import fetch_pdb, parse_pdb, protein_atoms

    verified = []
    for cand in TARGET_CANDIDATES:
        try:
            text = fetch_pdb(cand["pdb_id"])
            atoms = parse_pdb(text)
            prot = protein_atoms(atoms)
            from app.core.pdb import detect_ligands

            ligs = detect_ligands(atoms)
            chosen = None
            if cand.get("pocket_ligand"):
                chosen = next((l for l in ligs if l.resname == cand["pocket_ligand"]), None)
            if chosen is None and ligs:
                chosen = ligs[0]
            lig_desc = f"{chosen.resname} {chosen.resseq}:{chosen.chain}" if chosen else "none (ab-initio pocket)"
            cand = {**cand, "n_protein_atoms": len(prot),
                    "reference_ligand": lig_desc,
                    "n_ligand_atoms": len(chosen.atoms) if chosen else 0}
            verified.append(cand)
            print(f"  {cand['pdb_id']}: OK — {cand['name']} | ligand: {lig_desc}")
        except Exception as exc:
            print(f"  {cand.get('pdb_id')}: SKIPPED ({exc})")
        time.sleep(0.3)
    verified.sort(key=lambda c: c["priority"])
    with open(DATA_DIR / "targets.json", "w", encoding="utf-8") as fh:
        json.dump(verified, fh, indent=2)
    print(f"Targets written: {len(verified)} verified")


# --------------------------------------------------------------------------- #
# Curated literature evidence
# --------------------------------------------------------------------------- #

EVIDENCE = {
    "6LU7": [
        {"title": "Structure of Mpro from SARS-CoV-2 and discovery of its inhibitors (Jin et al., Nature 2020)", "url": "https://pubmed.ncbi.nlm.nih.gov/32354959/"},
        {"title": "PubChem search: Mpro inhibitors & repurposing screens", "url": "https://pubmed.ncbi.nlm.nih.gov/?term=SARS-CoV-2+Mpro+inhibitors+drug+repurposing"},
    ],
    "7BV2": [
        {"title": "Structural basis for remdesivir inhibition of SARS-CoV-2 RdRp (Yin et al., Science 2020)", "url": "https://pubmed.ncbi.nlm.nih.gov/?term=Yin+remdesivir+SARS-CoV-2+RNA+polymerase+structure"},
        {"title": "Remdesivir for Covid-19 — final report (Beigel et al., NEJM 2020)", "url": "https://pubmed.ncbi.nlm.nih.gov/32445940/"},
    ],
    "6M0J": [
        {"title": "Structure of the SARS-CoV-2 spike RBD bound to ACE2 (Lan et al., Nature 2020)", "url": "https://pubmed.ncbi.nlm.nih.gov/32225176/"},
    ],
    "1J3I": [
        {"title": "Plasmodium falciparum DHFR-TS structures with antifolates", "url": "https://pubmed.ncbi.nlm.nih.gov/?term=Plasmodium+falciparum+dihydrofolate+reductase+structure+inhibitor"},
    ],
    "2HU4": [
        {"title": "Structures of influenza A N1 neuraminidase with oseltamivir", "url": "https://pubmed.ncbi.nlm.nih.gov/?term=influenza+N1+neuraminidase+structure+oseltamivir"},
    ],
    "4EY7": [
        {"title": "Human acetylcholinesterase in complex with donepezil", "url": "https://pubmed.ncbi.nlm.nih.gov/?term=human+acetylcholinesterase+donepezil+crystal+structure"},
    ],
    "1HVR": [
        {"title": "HIV-1 protease structure and inhibitor design", "url": "https://pubmed.ncbi.nlm.nih.gov/?term=HIV-1+protease+crystal+structure+inhibitor"},
    ],
    "4M9K": [
        {"title": "Dengue NS2B-NS3 protease structures and inhibitor screening", "url": "https://pubmed.ncbi.nlm.nih.gov/?term=dengue+NS2B-NS3+protease+structure+inhibitor"},
    ],
    "5LC0": [
        {"title": "Zika virus NS3 helicase structures", "url": "https://pubmed.ncbi.nlm.nih.gov/?term=Zika+NS3+helicase+structure"},
    ],
    "1OHR": [
        {"title": "Hsp90 inhibitor complexes and resorcinol binding", "url": "https://pubmed.ncbi.nlm.nih.gov/?term=Hsp90+resorcinol+inhibitor+crystal+structure"},
    ],
    "_general": [
        {"title": "Drug repurposing: progress, challenges and recommendations (Pushpakom et al., Nat Rev Drug Discov 2019)", "url": "https://pubmed.ncbi.nlm.nih.gov/?term=Pushpakom+drug+repurposing+2019"},
        {"title": "A hybrid quantum computing pipeline for real world drug discovery (Li et al., 2024)", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11008569/"},
        {"title": "Quantum computing applications in drug discovery (review, 2026)", "url": "https://academic.oup.com/bib"},
        {"title": "VQE on the Hubbard dimer — Qiskit Nature tutorial", "url": "https://qiskit-community.github.io/qiskit-nature/"},
    ],
}


def build_evidence() -> None:
    with open(DATA_DIR / "evidence.json", "w", encoding="utf-8") as fh:
        json.dump(EVIDENCE, fh, indent=2)
    print(f"Evidence written: {len(EVIDENCE)} target entries")


if __name__ == "__main__":
    print("=" * 70)
    print("Q-Pharm data builder")
    print("=" * 70)
    stages = sys.argv[1:] or ["library", "ml", "targets", "evidence"]
    lib = None
    if "library" in stages:
        print("\n[1/4] Resolving drug SMILES from PubChem + validating with RDKit")
        lib = build_library()
    if "ml" in stages:
        print("\n[2/4] Training drug-likeness model")
        if lib is None:
            with open(DATA_DIR / "drug_library.json", "r", encoding="utf-8") as fh:
                lib = json.load(fh)
        train_model(lib)
    if "targets" in stages:
        print("\n[3/4] Verifying curated targets against RCSB")
        build_targets()
    if "evidence" in stages:
        print("\n[4/4] Writing literature evidence")
        build_evidence()
    print("\nDone.")
