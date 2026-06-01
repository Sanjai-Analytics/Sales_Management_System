import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import matplotlib.pyplot as plt

# --- 1. DATABASE CONNECTION ---
@st.cache_resource
def init_connection():
    try:
        return psycopg2.connect(
            host="localhost",
            user="postgres",     
            password="sanjai",  
            database="Sales_Mgt_Sys",   
            port="5432"
        )
    except Exception as e:
        st.error(f"Error connecting to PostgreSQL: {e}")
        return None

conn = init_connection()

# --- 2. AUTHENTICATION (LOGIN) ---
def login():
    # Safety check if database isn't connected
    if conn is None:
        st.error("Cannot connect to the database. Please check your credentials.")
        st.stop()

    st.title("Sales Management System")
    st.subheader("Login Portal")
    
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Based on user preference 
        query = "SELECT * FROM users WHERE username = %s AND password = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()
        
        if user:
            # Save all their details into Streamlit's memory
            st.session_state['logged_in'] = True
            st.session_state['user_id'] = user['user_id']
            st.session_state['branch_id'] = user['branch_id']
            st.session_state['username'] = user['username']
            
            # We are now saving their specific role (Admin or Super Admin)
            st.session_state['role'] = user['role'] 
            
            st.success(f"Login successful! Welcome, {user['role']}.")
            st.rerun()
        else:
            st.error("Invalid username or password.")

# --- 3. ADMIN DASHBOARD ---
def admin_dashboard():
    st.sidebar.title(f"Welcome, {st.session_state['username']}")
    st.sidebar.write(f"Branch ID: {st.session_state['branch_id']}")
    
    # Added 'Analytics & Reports' to the Admin navigation menu
    menu = st.sidebar.radio("Navigation", ["Dashboard Overview", "Add New Sale", "Record Payment", "Analytics & Reports"])
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    branch_id = st.session_state['branch_id']

    # --- VIEW: DASHBOARD OVERVIEW ---
    if menu == "Dashboard Overview":
        st.title("Branch Performance Overview")
        
        # Fetch Sales for this Admin's branch
        cursor.execute("SELECT * FROM customer_sales WHERE branch_id = %s", (branch_id,))
        sales_data = cursor.fetchall()
        
        if sales_data:
            df = pd.DataFrame(sales_data)
            
            # KPI Metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Gross Sales", f"₹{df['gross_sales'].sum():,.2f}")
            col2.metric("Total Received", f"₹{df['received_amount'].sum():,.2f}")
            col3.metric("Total Pending", f"₹{df['pending_amount'].sum():,.2f}")
            
            st.divider()
            st.subheader("Customer Sales Records")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No sales records found for your branch yet.")

    # --- VIEW: ADD NEW SALE ---
    elif menu == "Add New Sale":
        st.title("Register New Sale")
        
        with st.form("new_sale_form"):
            date = st.date_input("Sale Date")
            name = st.text_input("Customer Name")
            mobile = st.text_input("Mobile Number (10 digits)")
            product = st.text_input("Product Name")
            gross_sales = st.number_input("Gross Sales Amount (₹)", min_value=0.0, format="%.2f")
            
            submitted = st.form_submit_button("Submit Sale")
            
            if submitted:
                try:
                    
                    query = """SELECT setval(pg_get_serial_sequence('customer_sales', 'sale_id'), COALESCE(MAX(sale_id), 1)) FROM customer_sales;
                    INSERT INTO customer_sales (branch_id, date, name, mobile_number, product_name, gross_sales) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(query, (branch_id, date, name, mobile, product, gross_sales))
                    conn.commit()
                    st.success("New sale registered successfully!")
                except Exception as e:
                    conn.rollback() 
                    st.error(f"Failed to add sale: {e}")

    # --- VIEW: RECORD PAYMENT ---
    elif menu == "Record Payment":
        st.title("Record Payment Split")
        st.write("Record a new payment to automatically update the received and pending amounts.")
        
        # Fetch only 'Open' sales for this branch
        cursor.execute("SELECT sale_id, name, pending_amount FROM customer_sales WHERE branch_id = %s AND status = 'Open'", (branch_id,))
        open_sales = cursor.fetchall()
        
        if open_sales:
            # Create a dictionary to easily map the selection to the sale_id
            sale_options = {f"ID: {s['sale_id']} - {s['name']} (Pending: ₹{s['pending_amount']})": s['sale_id'] for s in open_sales}
            
            with st.form("payment_form"):
                selected_sale = st.selectbox("Select Sale", options=list(sale_options.keys()))
                payment_date = st.date_input("Payment Date")
                amount = st.number_input("Amount Paid (₹)", min_value=1.0, format="%.2f")
                method = st.selectbox("Payment Method", ["Cash", "Credit Card", "UPI", "Bank Transfer"])
                
                submitted = st.form_submit_button("Submit Payment")
                
                if submitted:
                    sale_id = sale_options[selected_sale]
                    try:
                        
                        query = """SELECT setval(pg_get_serial_sequence('payment_splits', 'payment_id'), COALESCE(MAX(payment_id), 1)) FROM payment_splits;
                        INSERT INTO payment_splits (sale_id, payment_date, amount_paid, payment_method) 
                        VALUES (%s, %s, %s, %s)
                        """
                        cursor.execute(query, (sale_id, payment_date, amount, method))
                        conn.commit()
                        st.success(f"Payment of ₹{amount} recorded! Sale amounts have been auto-updated.")
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Failed to record payment: {e}")
        else:
            st.info("There are no open sales pending payment for your branch.")

    # --- VIEW: ANALYTICS & REPORTS (ADMIN ONLY) ---
    elif menu == "Analytics & Reports":
        st.title("Branch Analytics & Reports")
        st.write("View performance metrics specific to your assigned branch.")
        
        report_option = st.selectbox(
            "Choose Analytics View:", 
            [
                "Option 1: Total Revenue by Branch (Quarterly)",
                "Option 2: Total Sales by Branch (Monthly)",
                "Option 3: Received vs Pending Amount (Pie Chart)"
            ]
        )
        
        st.divider()

        # Fetch available years for this specific branch
        cursor.execute("SELECT DISTINCT EXTRACT(YEAR FROM date) as year FROM customer_sales WHERE branch_id = %s ORDER BY year DESC", (branch_id,))
        db_years = cursor.fetchall()
        available_years = [str(int(y['year'])) for y in db_years] if db_years else ["2024"]

        # --- OPTION 1: Total Revenue by Branch (Quarterly) ---
        if report_option == "Option 1: Total Revenue by Branch (Quarterly)":
            st.subheader("Quarterly Revenue Breakdown")
            
            # Quarter Navigation Bar
            selected_q = st.radio("Select Quarter to view:", ["Q1", "Q2", "Q3", "Q4"], horizontal=True)
            quarter_num = int(selected_q[1]) 
            
            # Note: Because this is just one branch, I am grouping by Product Name so the chart is actually useful to look at!
            cursor.execute("""
                SELECT product_name, SUM(gross_sales) as revenue 
                FROM customer_sales 
                WHERE branch_id = %s AND EXTRACT(QUARTER FROM date) = %s
                GROUP BY product_name
            """, (branch_id, quarter_num))
            data = cursor.fetchall()
            
            if data:
                df = pd.DataFrame(data).set_index('product_name')
                total_q_revenue = df['revenue'].sum()
                
                st.metric(f"Total Revenue for {selected_q}", f"₹{total_q_revenue:,.2f}")
                st.bar_chart(df['revenue'])
            else:
                st.warning(f"No sales recorded for your branch in {selected_q}.")

        # --- OPTION 2: Total Sales by Branch (Monthly) ---
        elif report_option == "Option 2: Total Sales by Branch (Monthly)":
            st.subheader("Monthly Sales Breakdown")
            
            # Monthly Navigation Bar
            month_options = ["01 - January", "02 - February", "03 - March", "04 - April", "05 - May", "06 - June", "07 - July", "08 - August", "09 - September", "10 - October", "11 - November", "12 - December"]
            
            col1, col2 = st.columns(2)
            with col1:
                selected_year = st.selectbox("Select Year:", available_years)
            with col2:
                selected_month = st.selectbox("Select Month:", month_options)

            month_num = int(selected_month.split(" ")[0])
            
            # Grouping by Product Name to give a detailed visual breakdown
            cursor.execute("""
                SELECT product_name, SUM(gross_sales) as revenue 
                FROM customer_sales 
                WHERE branch_id = %s AND EXTRACT(YEAR FROM date) = %s AND EXTRACT(MONTH FROM date) = %s
                GROUP BY product_name
            """, (branch_id, int(selected_year), month_num))
            
            data = cursor.fetchall()
            
            if data:
                df = pd.DataFrame(data).set_index('product_name')
                total_m_sales = df['revenue'].sum()
                
                st.metric(f"Total Sales for {selected_month.split(' - ')[1]} {selected_year}", f"₹{total_m_sales:,.2f}")
                st.bar_chart(df['revenue'])
            else:
                st.info("No sales data available for this specific month.")

# --- OPTION 3: Received vs Pending (PIE CHART - MATPLOTLIB) ---
        elif report_option == "Option 3: Received vs Pending Amount (Pie Chart)":
            st.subheader("Branch Collection Status")
            
            # Fetch gross along with received and pending to calculate the exact percentage
            cursor.execute("""
                SELECT SUM(gross_sales) as gross, SUM(received_amount) as rcv, SUM(pending_amount) as pnd 
                FROM customer_sales 
                WHERE branch_id = %s
            """, (branch_id,))
            data = cursor.fetchone()
            
            if data and data['rcv'] is not None:
                # Calculate and display the pending percentage!
                pending_percentage = (data['pnd'] / data['gross']) * 100
                st.metric("Pending Collection Percentage", f"{pending_percentage:.1f}%")
                
                fig, ax = plt.subplots(figsize=(6, 6))
                labels = ['Received Amount', 'Pending Amount']
                sizes = [data['rcv'], data['pnd']]
                colors = ['#2ca02c', '#d62728'] 
                
                ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
                ax.axis('equal') 
                
                st.pyplot(fig)
            else:
                st.info("No financial data available to generate pie chart for your branch.")

# --- 4. SUPER ADMIN DASHBOARD ---
def super_admin_dashboard():
    st.sidebar.title(f"Welcome, {st.session_state['username']}")
    st.sidebar.write("Role: Super Admin")
    
    menu = st.sidebar.radio("Navigation", ["Company Overview", "Branch Performance", "Manage Branches", "Add New Sale", "All Sales Records", "Payment Split Details", "Analytics & Reports"])
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # --- VIEW: COMPANY OVERVIEW ---
    if menu == "Company Overview":
        st.title("Company Overview")
        
        # Fetch totals across ALL branches
        cursor.execute("""
            SELECT SUM(gross_sales) as t_gross, 
                   SUM(received_amount) as t_recv, 
                   SUM(pending_amount) as t_pend 
            FROM customer_sales
        """)
        totals = cursor.fetchone()
        
        if totals and totals['t_gross'] is not None:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Company Sales", f"₹{totals['t_gross']:,.2f}")
            col2.metric("Total Received", f"₹{totals['t_recv']:,.2f}")
            col3.metric("Total Pending", f"₹{totals['t_pend']:,.2f}")
        else:
            st.info("No sales data available in the system yet.")

    # --- VIEW: BRANCH PERFORMANCE ---
    elif menu == "Branch Performance":
        st.title("Branch-by-Branch Comparison")
        
        # Join tables to get branch names alongside their total sales
        query = """
            SELECT b.branch_name, 
                   SUM(c.gross_sales) as total_gross, 
                   SUM(c.received_amount) as total_received, 
                   SUM(c.pending_amount) as total_pending 
            FROM customer_sales c 
            JOIN branches b ON c.branch_id = b.branch_id 
            GROUP BY b.branch_name
        """
        cursor.execute(query)
        branch_data = cursor.fetchall()
        
        if branch_data:
            df = pd.DataFrame(branch_data)
            st.dataframe(df, use_container_width=True)
            
            st.subheader("Visual Comparison (Received vs Pending)")
            # Set branch name as index so the chart labels correctly
            chart_data = df.set_index("branch_name")[["total_received", "total_pending"]]
            st.bar_chart(chart_data)
        else:
            st.info("No branch data available.")

    # --- VIEW: MANAGE BRANCHES (SUPER ADMIN) ---
    elif menu == "Manage Branches":
        st.title("Manage Company Branches")
        
        # Create two tabs for a clean UI
        tab1, tab2 = st.tabs(["View All Branches", "Add New Branch"])
        
        # --- TAB 1: VIEW BRANCHES ---
        with tab1:
            st.subheader("Current Branch Directory")
            cursor.execute("SELECT branch_id, branch_name, branch_admin_name FROM branches ORDER BY branch_id")
            branches = cursor.fetchall()
            
            if branches:
                df_branches = pd.DataFrame(branches)
                st.dataframe(df_branches, use_container_width=True, hide_index=True)
            else:
                st.info("No branches found in the database.")
                
        # --- TAB 2: ADD NEW BRANCH ---
        with tab2:
            st.subheader("Register a New Branch")
            st.write("Add a new location to the company network.")
            
            with st.form("add_branch_form"):
                new_branch_name = st.text_input("Branch Name (e.g., Mumbai, Bangalore)")
                new_admin_name = st.text_input("Branch Admin Name (Manager's Name)")
                
                submitted = st.form_submit_button("Create Branch", type="primary")
                
                if submitted:
                    if new_branch_name and new_admin_name:
                        try:
                            # Safely insert the new branch into the database
                            query = """SELECT setval(pg_get_serial_sequence('branches', 'branch_id'),(SELECT MAX(branch_id) FROM branches));
                            INSERT INTO branches (branch_name, branch_admin_name) 
                            VALUES (%s, %s)
                            """
                            cursor.execute(query, (new_branch_name, new_admin_name))
                            conn.commit()
                            
                            st.success(f"Successfully created the {new_branch_name} branch!")
                            # Rerun to refresh the "View All Branches" tab instantly
                            st.rerun() 
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Failed to add branch: {e}")
                    else:
                        st.warning("Please fill out both the Branch Name and Admin Name.")        

    # --- VIEW: ADD NEW SALE (SUPER ADMIN) ---
    elif menu == "Add New Sale":
        st.title("Register New Sale")
        st.write("As a Super Admin, you can assign sales to any branch.")
        
        # Fetch all branches for the dropdown
        cursor.execute("SELECT branch_id, branch_name FROM branches")
        branches = cursor.fetchall()
        
        if branches:
            branch_options = {b['branch_name']: b['branch_id'] for b in branches}
            
            with st.form("super_admin_new_sale_form"):
                selected_branch = st.selectbox("Select Branch", options=list(branch_options.keys()))
                date = st.date_input("Sale Date")
                name = st.text_input("Customer Name")
                mobile = st.text_input("Mobile Number (10 digits)")
                product = st.text_input("Product Name")
                gross_sales = st.number_input("Gross Sales Amount (₹)", min_value=0.0, format="%.2f")
                
                submitted = st.form_submit_button("Submit Sale")
                
                if submitted:
                    branch_id = branch_options[selected_branch]
                    try:
                        query = """SELECT setval(pg_get_serial_sequence('customer_sales', 'sale_id'), COALESCE(MAX(sale_id), 1)) FROM customer_sales;
                        INSERT INTO customer_sales (branch_id, date, name, mobile_number, product_name, gross_sales) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(query, (branch_id, date, name, mobile, product, gross_sales))
                        conn.commit()
                        st.success(f"New sale registered successfully for {selected_branch}!")
                    except Exception as e:
                        conn.rollback() 
                        st.error(f"Failed to add sale. (Make sure the mobile number is unique!): {e}")
        else:
            st.error("No branches found in the database. Please add branches first.")            

    # --- VIEW: ALL SALES RECORDS ---
    elif menu == "All Sales Records":
        st.title("Global Sales Database")
        
        # Fetch every sale, including which branch made it
        query = """
            SELECT c.sale_id, b.branch_name, c.date, c.name, c.mobile_number, 
                   c.product_name, c.gross_sales, c.pending_amount, c.status 
            FROM customer_sales c 
            JOIN branches b ON c.branch_id = b.branch_id 
            ORDER BY c.date DESC
        """
        cursor.execute(query)
        all_sales = cursor.fetchall()
        
                
        if all_sales:
            # df = pd.DataFrame(all_sales)
            df=pd.DataFrame(all_sales)
            st.data_editor(
            df, 
            num_rows="fixed", 
            use_container_width=True,
            key="sales_editor",
            disabled=["sale_id", "branch_name"]
        )
            
            # --- THE SAVE BUTTON ---
            if st.button("Save All Changes to Database", type="primary"):
                # Grab the dictionary of changes from Streamlit's memory
                changes = st.session_state["sales_editor"]
                
                try:
                    # 1. PROCESS EDITS
                    for row_idx, updated_cols in changes["edited_rows"].items():
                        # Find the actual sale_id for the row that was edited
                        sale_id = int(df.iloc[row_idx]["sale_id"])
                        
                        # Loop through only the specific columns that were changed
                        for col_name, new_value in updated_cols.items():
                            query = f"""SELECT setval(pg_get_serial_sequence('customer_sales', 'sale_id'), COALESCE(MAX(sale_id), 1)) FROM customer_sales;
                            UPDATE customer_sales SET {col_name} = %s WHERE sale_id = %s"""
                            cursor.execute(query, (new_value, sale_id))
                    
                    # 2. PROCESS DELETIONS
                    for row_idx in changes["deleted_rows"]:
                        # Find the sale_id of the deleted row
                        sale_id = int(df.iloc[row_idx]["sale_id"])
                        
                        query = """SELECT setval(pg_get_serial_sequence('customer_sales', 'sale_id'), COALESCE(MAX(sale_id), 1)) FROM customer_sales;
                        DELETE FROM customer_sales WHERE sale_id = %s"""
                        cursor.execute(query, (sale_id,))
                        
                    # 3. PROCESS ADDITIONS (New Rows)
                    for new_row in changes["added_rows"]:
                        # Get column names and values dynamically
                        columns = ', '.join(new_row.keys())
                        placeholders = ', '.join(['%s'] * len(new_row))
                        values = tuple(new_row.values())
                        
                        query = f"""SELECT setval(pg_get_serial_sequence('customer_sales', 'sale_id'), COALESCE(MAX(sale_id), 1)) FROM customer_sales;
                        INSERT INTO customer_sales ({columns}) VALUES ({placeholders})"""
                        cursor.execute(query, values)

                    # --- CRITICAL: COMMIT AND REFRESH ---
                    conn.commit()  
                    st.success("Database successfully updated!")
                    st.rerun()     # Refresh the screen so the table matches the new database

                except Exception as e:
                    conn.rollback() # If anything fails, cancel the whole transaction
                    st.error(f"Failed to update database: {e}")
                    
            else:
                st.info("No sales records found.")
        else:
            st.info("No sales records found.")    

# --- VIEW: Payment Split Details ---
    elif menu == "Payment Split Details":
        st.title("Manage Payment Splits")
        tab1, tab2 = st.tabs(["View & Edit Payments", "Record New Payment"])
    
        # --- TAB 1: VIEW & EDIT PAYMENTS ---
        with tab1:
            st.subheader("Global Payment Splits Database")
        query = """
            SELECT p.payment_id, p.sale_id, p.payment_date, p.amount_paid, payment_method,
            c.name, c.mobile_number, c.product_name,
            c.gross_sales, c.pending_amount, c.status  
            FROM payment_splits p
            LEFT JOIN customer_sales c ON p.sale_id = c.sale_id
        """
        cursor.execute(query)
        all_Payment_splits = cursor.fetchall()
        
        if all_Payment_splits:
        
            df=pd.DataFrame(all_Payment_splits)
            st.data_editor(
            df, 
            num_rows="fixed", 
            use_container_width=True,
            key="Payment_editor",
            disabled=["sale_id", "payment_id", "name", "mobile_number", 
                    "product_name", "gross_sales", "pending_amount", "status"]
        )
            
            # --- THE SAVE BUTTON ---
            if st.button("Save All Changes to Database", type="primary"):
                # Grab the dictionary of changes from Streamlit's memory
                changes = st.session_state["Payment_editor"]
                
                try:
                    # 1. PROCESS EDITS
                    for row_idx, updated_cols in changes["edited_rows"].items():
                        # Find the actual sale_id for the row that was edited
                        payment_id = int(df.iloc[row_idx]["payment_id"])
                        
                        # Loop through only the specific columns that were changed
                        for col_name, new_value in updated_cols.items():
                            query = f"""SELECT setval(pg_get_serial_sequence('payment_splits', 'payment_id'), COALESCE(MAX(payment_id), 1)) FROM payment_splits;
                            UPDATE payment_splits SET {col_name} = %s WHERE payment_id = %s"""
                            cursor.execute(query, (new_value, payment_id))
                    
                    # 2. PROCESS DELETIONS
                    for row_idx in changes["deleted_rows"]:
                        # Find the sale_id of the deleted row
                        payment_id = int(df.iloc[row_idx]["payment_id"])
                        
                        query = """SELECT setval(pg_get_serial_sequence('payment_splits', 'payment_id'), COALESCE(MAX(payment_id), 1)) FROM payment_splits;
                        DELETE FROM payment_splits WHERE payment_id = %s"""
                        cursor.execute(query, (payment_id,))
                        
                    # 3. PROCESS ADDITIONS (New Rows)
                    for new_row in changes["added_rows"]:
                        # Get column names and values dynamically
                        columns = ', '.join(new_row.keys())
                        placeholders = ', '.join(['%s'] * len(new_row))
                        values = tuple(new_row.values())
                        
                        query = f"""SELECT setval(pg_get_serial_sequence('payment_splits', 'payment_id'), COALESCE(MAX(payment_id), 1)) FROM payment_splits;
                        INSERT INTO payment_splits ({columns}) VALUES ({placeholders})"""
                        cursor.execute(query, values)

                    # --- CRITICAL: COMMIT AND REFRESH ---
                    conn.commit()  
                    st.success("Database successfully updated!")
                    st.rerun()     # Refresh the screen so the table matches the new database

                except Exception as e:
                    conn.rollback() # If anything fails, cancel the whole transaction
                    st.error(f"Failed to update database: {e}")
                    
        else:
            st.info("No Payment Split records found.")

# --- TAB 2: RECORD NEW PAYMENT ---
        with tab2:
            st.subheader("Apply Payment to Open Sale")
            st.write("Record a new split payment.")
            
            # Fetch open sales across ALL branches.
            cursor.execute("""
                SELECT c.sale_id, c.name, c.pending_amount, b.branch_name 
                FROM customer_sales c
                JOIN branches b ON c.branch_id = b.branch_id
                WHERE c.status = 'Open'
            """)
            open_sales = cursor.fetchall()
            
            if open_sales:
                # Format the dropdown so it clearly shows the Customer, Branch, and Pending Amount
                sale_options = {
                    f"ID: {s['sale_id']} - {s['name']} ({s['branch_name']}) | Pending: ₹{s['pending_amount']}": s['sale_id'] 
                    for s in open_sales
                }
                
                with st.form("super_admin_payment_form"):
                    selected_sale = st.selectbox("Select Sale", options=list(sale_options.keys()))
                    payment_date = st.date_input("Payment Date")
                    amount = st.number_input("Amount Paid (₹)", min_value=1.0, format="%.2f")
                    method = st.selectbox("Payment Method", ["Cash", "Credit Card", "UPI", "Bank Transfer"])
                    
                    submitted = st.form_submit_button("Submit Payment", type="primary")
                    
                    if submitted:
                        sale_id = sale_options[selected_sale]
                        try:
                            query = """SELECT setval(pg_get_serial_sequence('payment_splits', 'payment_id'), COALESCE(MAX(payment_id), 1)) FROM payment_splits;
                            INSERT INTO payment_splits (sale_id, payment_date, amount_paid, payment_method) 
                            VALUES (%s, %s, %s, %s)
                            """
                            cursor.execute(query, (sale_id, payment_date, amount, method))
                            conn.commit()
                            
                            st.success(f"Payment of ₹{amount} recorded successfully!")
                            st.rerun() 
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Failed to record payment: {e}")
            else:
                st.info("There are currently no open sales pending payment across any branches.")

# --- VIEW: ANALYTICS & REPORTS ---
    elif menu == "Analytics & Reports":
        st.title("Business Analytics & Reports")
        
        tab1, tab2 = st.tabs(["Interactive Analytics", "Export Data"])
        
        with tab1:
            st.subheader("Select a Report to View")
            
            report_option = st.selectbox(
                "Choose Analytics View:", 
                [
                    "Option 1: Revenue based on Branches (Selected Period)",
                    "Option 2: Quarter-wise Revenue based on Branches",
                    "Option 3: Payment Methods based on Branches",
                    "Option 4: Total Received vs Total Pending (Pie Chart)",
                    "Option 5: Sales based on Products (Selected Period)",
                    "Option 6: Financial KPI Summary"
                ]
            )
            
            st.divider()

            # Fetch available years directly from the database for our navigation bars
            cursor.execute("SELECT DISTINCT EXTRACT(YEAR FROM date) as year FROM customer_sales ORDER BY year DESC")
            db_years = cursor.fetchall()
            available_years = [str(int(y['year'])) for y in db_years] if db_years else ["2024"]
            month_options = ["All Year", "01 - January", "02 - February", "03 - March", "04 - April", "05 - May", "06 - June", "07 - July", "08 - August", "09 - September", "10 - October", "11 - November", "12 - December"]

            # --- OPTION 1: Revenue based on Branches (No Dates on Axis) ---
            if report_option == "Option 1: Revenue based on Branches (Selected Period)":
                st.subheader("Branch Performance")
                
                col1, col2 = st.columns(2)
                with col1:
                    selected_year = st.selectbox("Select Year:", available_years, key="opt1_year")
                with col2:
                    selected_month = st.selectbox("Select Month:", month_options, key="opt1_month")

                if selected_month == "All Year":
                    query_filter = "WHERE EXTRACT(YEAR FROM c.date) = %s"
                    params = [int(selected_year)]
                else:
                    month_num = int(selected_month.split(" ")[0])
                    query_filter = "WHERE EXTRACT(YEAR FROM c.date) = %s AND EXTRACT(MONTH FROM c.date) = %s"
                    params = [int(selected_year), month_num]

                # Notice the date has been completely removed from the SELECT and GROUP BY!
                cursor.execute(f"""
                    SELECT b.branch_name, SUM(c.gross_sales) as revenue
                    FROM customer_sales c
                    JOIN branches b ON c.branch_id = b.branch_id
                    {query_filter}
                    GROUP BY b.branch_name 
                    ORDER BY revenue DESC
                """, tuple(params))
                
                data = cursor.fetchall()
                if data:
                    df = pd.DataFrame(data).set_index('branch_name')
                    st.bar_chart(df['revenue'])
                else:
                    st.info("No branch revenue data available for this period.")

            # --- OPTION 2: Quarter-wise Revenue based on Branches ---
            elif report_option == "Option 2: Quarter-wise Revenue based on Branches":
                st.subheader("Quarterly Branch Performance")
                
                selected_q = st.radio("Select Quarter to view:", ["Q1", "Q2", "Q3", "Q4"], horizontal=True)
                quarter_num = int(selected_q[1]) 
                
                cursor.execute("""
                    SELECT b.branch_name, SUM(c.gross_sales) as revenue 
                    FROM customer_sales c
                    JOIN branches b ON c.branch_id = b.branch_id
                    WHERE EXTRACT(QUARTER FROM c.date) = %s
                    GROUP BY b.branch_name
                """, (quarter_num,))
                data = cursor.fetchall()
                
                if data:
                    df = pd.DataFrame(data).set_index('branch_name')
                    st.bar_chart(df['revenue'])
                else:
                    st.warning(f"No sales found across any branches in {selected_q}.")

            # --- OPTION 3: Payment Methods based on Branches ---
            elif report_option == "Option 3: Payment Methods based on Branches":
                st.subheader("Payment Methods by Branch")
                cursor.execute("""
                    SELECT b.branch_name, p.payment_method, COUNT(p.payment_id) as usage_count 
                    FROM payment_splits p
                    JOIN customer_sales c ON p.sale_id = c.sale_id
                    JOIN branches b ON c.branch_id = b.branch_id
                    GROUP BY b.branch_name, p.payment_method
                """)
                data = cursor.fetchall()
                if data:
                    df = pd.DataFrame(data)
                    pivot_df = df.pivot(index='branch_name', columns='payment_method', values='usage_count').fillna(0)
                    st.bar_chart(pivot_df)
                else:
                    st.info("No payment split data available.")

            # --- OPTION 4: Received vs Pending (PIE CHART) ---
            elif report_option == "Option 4: Total Received vs Total Pending (Pie Chart)":
                st.subheader("Revenue Collection Status")
                cursor.execute("SELECT SUM(gross_sales) as gross, SUM(received_amount) as rcv, SUM(pending_amount) as pnd FROM customer_sales")
                data = cursor.fetchone()
                
                if data and data['rcv'] is not None:
                    pending_percentage = (data['pnd'] / data['gross']) * 100
                    st.metric("Pending Collection Percentage", f"{pending_percentage:.1f}%")
                    
                    fig, ax = plt.subplots(figsize=(6, 6))
                    labels = ['Received Amount', 'Pending Amount']
                    sizes = [data['rcv'], data['pnd']]
                    colors = ['#2ca02c', '#d62728'] 
                    
                    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
                    ax.axis('equal') 
                    st.pyplot(fig)
                else:
                    st.info("No financial data available to generate pie chart.")

            # --- OPTION 5: Sales Trends based on Products (No Dates on Axis) ---
            elif report_option == "Option 5: Sales based on Products (Selected Period)":
                st.subheader("Product Performance")
                
                col1, col2 = st.columns(2)
                with col1:
                    selected_year = st.selectbox("Select Year:", available_years, key="opt5_year")
                with col2:
                    selected_month = st.selectbox("Select Month:", month_options, key="opt5_month")

                if selected_month == "All Year":
                    query_filter = "WHERE EXTRACT(YEAR FROM date) = %s"
                    params = [int(selected_year)]
                else:
                    month_num = int(selected_month.split(" ")[0])
                    query_filter = "WHERE EXTRACT(YEAR FROM date) = %s AND EXTRACT(MONTH FROM date) = %s"
                    params = [int(selected_year), month_num]

                # Notice the date has been completely removed from the SELECT and GROUP BY!
                cursor.execute(f"""
                    SELECT product_name, SUM(gross_sales) as sales 
                    FROM customer_sales
                    {query_filter}
                    GROUP BY product_name 
                    ORDER BY sales DESC
                """, tuple(params))
                
                data = cursor.fetchall()
                if data:
                    df = pd.DataFrame(data).set_index('product_name')
                    st.bar_chart(df['sales'])
                else:
                    st.info("No product data available for this period.")

            # --- OPTION 6: Financial KPI Summary ---
            elif report_option == "Option 6: Financial KPI Summary":
                st.subheader("Global Financial KPIs")
                cursor.execute("""
                    SELECT SUM(gross_sales) as t_gross, 
                           SUM(received_amount) as t_recv, 
                           SUM(pending_amount) as t_pend 
                    FROM customer_sales
                """)
                kpi_data = cursor.fetchone()
                
                if kpi_data and kpi_data['t_gross'] is not None:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric(label="Total Company Sales", value=f"₹{kpi_data['t_gross']:,.2f}")
                    with col2:
                        st.metric(label="Total Received Amount", value=f"₹{kpi_data['t_recv']:,.2f}")
                    with col3:
                        st.metric(label="Total Pending Amount", value=f"₹{kpi_data['t_pend']:,.2f}")
                else:
                    st.info("No sales data available to calculate KPIs.")

        # --- TAB 2: EXPORT DATA ---
        with tab2:
            st.subheader("Download Raw Data")
            cursor.execute("""
                SELECT c.sale_id, b.branch_name, c.date, c.name, c.product_name, 
                       c.gross_sales, c.received_amount, c.pending_amount, c.status 
                FROM customer_sales c JOIN branches b ON c.branch_id = b.branch_id ORDER BY c.date DESC
            """)
            report_data = cursor.fetchall()
            
            if report_data:
                df_report = pd.DataFrame(report_data)
                st.dataframe(df_report.head(5), use_container_width=True) 
                csv = df_report.to_csv(index=False).encode('utf-8')
                st.download_button("Download Full Database (CSV)", data=csv, file_name='SuperAdmin_Sales.csv', mime='text/csv', type='primary')
            else:
                st.warning("No data available to export.")

if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()        


# --- 5. APP ROUTING ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if st.session_state['logged_in']:
    # Check the role we saved during login!
    if st.session_state.get('role') == 'Super Admin':
        super_admin_dashboard()
    else:
        admin_dashboard()
else:
    login()