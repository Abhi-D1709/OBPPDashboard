import streamlit as st
import pandas as pd
import requests
import json
from io import BytesIO

# Set page configuration
st.set_page_config(page_title="OBPP Dashboard", page_icon="📊", layout="wide")

# Function to load data from Google Sheets CSV
def load_data_from_gsheet(url):
    return pd.read_csv(url)

# Function to check ISIN status and get company names
def check_isin_status_and_company(isins):
    api_url = "https://api.openfigi.com/v3/mapping"
    api_key = "32260fb5-c33b-4032-9abe-98f3c26f665a"
    headers = {
        'Content-Type': 'application/json',
        'X-OPENFIGI-APIKEY': api_key
    }
    
    payload = json.dumps([{"idType": "ID_ISIN", "idValue": isin} for isin in isins])
    
    try:
        response = requests.post(api_url, headers=headers, data=payload)
        response.raise_for_status()
        data = response.json()
        
        results = {}
        
        for isin, item in zip(isins, data):
            company_name = "Unknown"
            listing_status = "Unlisted"
            if 'data' in item and len(item['data']) > 0:
                company_name = item['data'][0].get('name', "Unknown")
                exch_code = item['data'][0].get('exchCode', None)
                if exch_code and exch_code != 'NOT LISTED':
                    listing_status = "Listed"
            results[isin] = (company_name, listing_status)
        
        return results
    
    except requests.exceptions.RequestException as err:
        return {isin: ("Error", "Error") for isin in isins}

# Function to load the broker list into a DataFrame
@st.cache_data
def load_broker_data():
    SEBI_URL = "https://www.sebi.gov.in/sebiweb/other/IntmExportAction.do?intmId=37"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9,en-IN;q=0.8",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Host": "www.sebi.gov.in",
        "Origin": "https://www.sebi.gov.in",
        "Referer": "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognised=yes",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
        "sec-ch-ua": '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    try:
        response = requests.post(SEBI_URL, headers=headers)
        response.raise_for_status()

        excel_data = BytesIO(response.content)
        df_broker = pd.read_excel(excel_data, header=2)

        df_broker.drop_duplicates(subset='Registration No.', keep='first', inplace=True)
        return df_broker

    except requests.exceptions.RequestException as e:
        st.error("Failed to download broker list.")
        st.write(e)
        return None

# Function to search brokers by name
def search_broker(df_broker, name):
    result = df_broker[df_broker['Name'].str.contains(name, case=False, na=False)]
    return result[['Name', 'Registration No.', 'Address', 'From']]

# Navigation using a dropdown
st.sidebar.title("Navigation")
page = st.sidebar.selectbox("Go to", ["Home", "Compliance Status", "Check ISIN Listing Status", "Check Broker Registration"])

# Home Page
if page == "Home":
    st.markdown("<h1 style='text-align: center; color: #4A90E2;'>OBPP Dashboard</h1>", unsafe_allow_html=True)
    
    # Load and display data from the first Google Sheet
    gsheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSDNS01NBHBP4cJ_7_q0OTIuVf1AY_QNoER6tUi7kfVjGsRamCDcWGuP7cgO5k6Fw/pub?output=csv"
    df = load_data_from_gsheet(gsheet_url)
    st.dataframe(df)

# Compliance Status Page
elif page == "Compliance Status":
    st.markdown("<h1 style='text-align: center; color: #4A90E2;'>Compliance Status</h1>", unsafe_allow_html=True)
    
    # Load and display data from the second Google Sheet
    gsheet_url_status = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQcDBUZMQ1qXQ7drsmMx1ge8EsFCML1vcjgr-Yttsy2MdKrOGGh23_nav2uL9L82w/pub?output=csv"
    df_status = load_data_from_gsheet(gsheet_url_status)
    st.dataframe(df_status)

# Check ISIN Listing Status Page
elif page == "Check ISIN Listing Status":
    st.markdown("<h1 style='text-align: center; color: #4A90E2;'>Check ISIN Listing Status</h1>", unsafe_allow_html=True)
    
    # File uploader for Excel files
    uploaded_file = st.file_uploader("Choose an Excel file", type="xlsx")
    
    if uploaded_file is not None:
        if st.button("Upload"):
            st.markdown('<div style="color:#4A90E2;">Processing the file...</div>', unsafe_allow_html=True)
            
            # Read the uploaded Excel file
            df = pd.read_excel(uploaded_file)
            
            # Check for the ISIN column
            if 'ISIN' in df.columns:
                # Process the ISINs in the file
                isins = df['ISIN'].tolist()
                batch_size = 100
                results = {}

                for i in range(0, len(isins), batch_size):
                    batch_isins = isins[i:i+batch_size]
                    batch_results = check_isin_status_and_company(batch_isins)
                    results.update(batch_results)

                # Update the DataFrame with company names and listing statuses
                df['Company Name'] = df['ISIN'].map(lambda x: results[x][0])
                df['Listed/ Unlisted'] = df['ISIN'].map(lambda x: results[x][1])

                # Convert DataFrame to Excel for download
                towrite = BytesIO()
                df.to_excel(towrite, index=False, engine='openpyxl')
                towrite.seek(0)
                processed_file = towrite

                st.success("Processing completed!")
                st.download_button(
                    label="Download Processed File",
                    data=processed_file,
                    file_name="processed_file.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("The uploaded file does not contain an 'ISIN' column. Please check your file.")

# Check Broker Registration Page
elif page == "Check Broker Registration":
    st.markdown("<h1 style='text-align: center; color: #4A90E2;'>Check Broker Registration</h1>", unsafe_allow_html=True)
    
    # Load the broker data from the SEBI website
    df_broker = load_broker_data()

    if df_broker is not None:
        # Input for broker name
        broker_name = st.text_input("Enter the first few letters of the broker's name")

        # Search and display the results
        if broker_name:
            search_results = search_broker(df_broker, broker_name)
            if not search_results.empty:
                st.write("Search Results:")
                st.dataframe(search_results)
            else:
                st.warning("No brokers found with that name.")
    else:
        st.error("Unable to load broker data.")

# Footer
st.markdown('<div style="text-align: center; padding: 10px;">Developed by Abhignan</div>', unsafe_allow_html=True)
