# BacDoc 🧫  
**A Database-Driven Platform for Bacterial Identification and Culture Media Recommendation**

[![License](https://img.shields.io/github/license/StressedUnderAMountain/BacDoc)](LICENSE)  
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)  
[![Flask](https://img.shields.io/badge/framework-Flask-black)](https://flask.palletsprojects.com/)  
[![Status](https://img.shields.io/badge/status-Research%20Prototype-yellow)](https://github.com/StressedUnderAMountain/BacDoc)

BacDoc is a free, web-based microbiology support platform that assists with **bacterial identification and cultivation media prediction**, especially for **resource-limited laboratories and educational settings**. Unlike expensive commercial systems, BacDoc connects **organism identification directly to optimized growth media recommendations**, including automatic volume scaling and hybrid media generation for unknown organisms.

---

## 🔬 Why BacDoc?
- Advanced diagnostic systems like MALDI-TOF and VITEK 2 are expensive and inaccessible in many labs.
- Over **99% of bacteria cannot be cultured using standard media**.
- Existing databases list media recipes but do not **automatically link identification to cultivation guidance**.

**BacDoc bridges this gap.**

---

## ✨ Key Features
- 🔍 **Fuzzy organism name matching** (handles spelling errors)
- 🧪 **Automated growth media recommendation**
- 📏 **Automatic media scaling** (100 mL → 2 L+)
- 🧬 **Unknown organism handling** using phenotypic similarity scoring
- 🧩 **Hybrid media generation** from closest matching organisms
- 🌐 **Web-based interface** built with Flask
- 💾 **Database:** Centraldatabase.csv (~800 species)
- 💸 **Completely free & open-source**

---

## 🧠 How It Works (Conceptual)
1. User enters an organism name **or**
2. Provides phenotypic parameters for unknown organisms  
   (Gram reaction, morphology, oxygen requirement, pH, temperature, origin)
3. A **rule-based weighted distance algorithm** identifies closest matches
4. Media compositions are retrieved, merged, and scaled automatically

⚠️ This is a **rule-based research prototype**, not an AI or clinical diagnostic tool.

---

## 🛠️ Tech Stack
- **Backend:** Python, Flask
- **Frontend:** HTML, CSS, JavaScript
- **Database:** CSV-based curated microbiology dataset (~800 species)
- **Algorithms:** Fuzzy string matching + weighted phenotypic distance scoring

---

## 🚀 Running Locally
```bash
git clone https://github.com/StressedUnderAMountain/BacDoc.git
cd BacDoc
pip install -r requirements.txt
PhytonAILLm.py 
 ```
Then open: http://0.0.0.0:5000 

---

## 📚 Academic Context
Developed as part of a B.Sc. Microbiology dissertation  
**Karmaveer Bhaurao Patil College, Navi Mumbai**  
University of Mumbai (2024–2025).

## ⚠️ Disclaimer
BacDoc is intended for educational and research use only.  
It is not a clinical diagnostic system.  
All recommendations require experimental validation.

## 📄 License
[MIT License](LICENSE) — see LICENSE file for details.

## 👤 Author
**Preston Joshua Menezes**  
Microbiology | Computational Biology | Open Science
