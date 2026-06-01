# Sales_Management_System
# 🏢 Multi-Branch Sales Management System

A robust, role-based full-stack web application built with Python and Streamlit, designed to manage sales, track revenue, and monitor payment collections across multiple company branches. 

This system features a secure authentication portal, role-based access control (RBAC), and dynamic, data-driven analytical dashboards powered by PostgreSQL and Pandas.

## ✨ Key Features

* **Role-Based Access Control (RBAC):**
  * **Super Admin:** Global oversight. Manage branch directories, view company-wide KPIs, and analyze performance across all branches.
  * **Branch Admin:** Localized access. Register sales and record split payments exclusively for their assigned branch.
* **Dynamic Payment Tracking:** Automatically calculates and updates pending balances when partial or split payments are recorded.
* **Interactive Dashboards:** * Clean, multi-page navigation using Streamlit's modern routing (`st.navigation`).
  * Editable data grids to safely update or delete database records directly from the UI.
* **Advanced Analytics & Reporting:**
  * Interactive Dropdowns (Year/Month/Quarter) to instantly drill down into specific timeframes.
  * Visual branch-to-branch revenue comparisons.
  * KPI Metric Cards and Matplotlib-generated Pie Charts for pending collection percentages.

## 🛠️ Tech Stack

* **Frontend:** [Streamlit](https://streamlit.io/) (Multi-page app architecture)
* **Backend:** Python 3.x
* **Database:** PostgreSQL (Connected via `psycopg2` using `RealDictCursor` for dictionary mapping)
* **Data Processing:** Pandas
* **Data Visualization:** Matplotlib, Streamlit Native Charts

## 📂 Project Structure

The application is architected for scalability and security, separating global routing from localized page views.

```text
📁 Sales-Management-System
│
├── main.py                    # DB Connection, Login Auth & Route Traffic Controller
├── super_admin.py             # Super Admin navigation mapper
├── admin.py                   # Branch Admin navigation mapper
├── requirements.txt           # Python dependencies
│
└── 📁 pages/                  # Isolated UI Views
    ├── Admin_Add_New_Sale.py
    ├── Admin_Analytics_Reports.py
    ├── Admin_Dashboard_Overview.py
    ├── All_Sales_Records.py
    ├── Branch_Performance.py
    ├── Company_Overview.py
    ├── Manage_Branches.py
    ├── Payment_Split_Details.py
    ├── Record_Payment.py
    ├── SA_Add_New_Sale.py
    └── SA_Analytics_Reports.py
