#!/bin/bash
# Start all 4 services

# Cleanup trap to prevent zombie processes
trap "echo 'Shutting down servers...'; pkill -f 'flask run'; pkill -f 'python3 app.py'; exit" INT TERM EXIT

# Set PYTHONPATH so child apps can import from the root 'services' folder
export PYTHONPATH=$(pwd)
export ONEDRIVE_SHARE_URL="https://horusuni-my.sharepoint.com/:f:/g/personal/aelshafee_horus_edu_eg/IgD0qoF1DQWTSqbxLv0Ccb5gAe65TdO255mPl-HXKm078jo"
export ONEDRIVE_PREVIEW_SHARE_URL="https://horusuni-my.sharepoint.com/:f:/g/personal/aelshafee_horus_edu_eg/IgB8bbTxDL1DSbc_8o2geGwTAY4tuq4OTEUwSWSPHfhL8b8?e=n5UMBa"
export FERNET_KEY="L0E_NAQjJiC0Pqc-8R_zODA2hsHIjTJlZq26eOqLk4M="

echo "Starting Gateway..."
cd Gateway
python3 app.py &
cd ..

echo "Starting Essic..."
cd core_app
export FLASK_RUN_PORT=5001
export SYSTEM_ORG_NAME="مدير مركز الخدمات الإلكترونية"
export SYSTEM_ORG_EXAMPLE="كلية الهندسة"
export SYSTEM_MANAGER_SIG="مدير مركز الخدمات الإلكترونية"
export SYSTEM_MANAGER_NAME="محمد كمال عبد السلام"
export SYSTEM_OFFICE_CODE="ESSIC"
export SYSTEM_TEMPLATE_FILENAME="template_essic.docx"
export SYSTEM_PREVIEW_BG="assets/doc_image3.png"
export SYSTEM_PREVIEW_FOOTER="assets/image4.png"
export SYSTEM_PREVIEW_PT="18%"
export SYSTEM_KNOWN_ABBRS="ESSIC,HUE,IT,HR"
export SYSTEM_ONEDRIVE_FOLDER="/personal/aelshafee_horus_edu_eg/Documents/ESSIC_Docs"
export SUPABASE_DB_URL="postgresql+psycopg://postgres.spjivemssfkebihjfvae:mXP%248u73SQNNM6D@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"
python3 -m flask run --port=5001 &
cd ..

echo "Starting Faculty of Engineering..."
cd core_app
export FLASK_RUN_PORT=5002
export SYSTEM_ORG_NAME="وكيل كلية الهندسة"
export SYSTEM_ORG_EXAMPLE="وكيل كلية الهندسة"
export SYSTEM_MANAGER_SIG="وكيل كلية الهندسة"
export SYSTEM_OFFICE_CODE="HUEED"
export SYSTEM_TEMPLATE_FILENAME="template_vice_dean.docx"
export SYSTEM_PREVIEW_BG="assets/vice_dean_bg.png"
export SYSTEM_PREVIEW_FOOTER="assets/blank.png"
export SYSTEM_PREVIEW_PT="22%"
export SYSTEM_KNOWN_ABBRS="Faculty of Engineering Vice Dean,HUE,IT,HR"
export SYSTEM_ONEDRIVE_FOLDER="/personal/aelshafee_horus_edu_eg/Documents/Faculty_of_Engineering_Docs"
export SUPABASE_DB_URL="postgresql+psycopg://postgres.ucxlldcmvguetxjgghfx:8wD.xVc4s%3DxdA6P@aws-1-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require"
python3 -m flask run --port=5002 &
cd ..

echo "Starting Artificial Engineering Department (AIE)..."
cd core_app
export FLASK_RUN_PORT=5003
export SYSTEM_ORG_NAME="رئيس قسم هندسة الذكاء الاصطناعي"
export SYSTEM_ORG_EXAMPLE="كلية الهندسة"
export SYSTEM_MANAGER_SIG="رئيس قسم هندسة الذكاء الاصطناعي"
export SYSTEM_OFFICE_CODE="AIE"
export SYSTEM_TEMPLATE_FILENAME="template_aie.docx"
export SYSTEM_PREVIEW_BG="assets/aie_bg.png"
export SYSTEM_PREVIEW_FOOTER="assets/blank.png"
export SYSTEM_PREVIEW_PT="28%"
export SYSTEM_KNOWN_ABBRS="ESSIC,HUE,IT,HR"
export SYSTEM_ONEDRIVE_FOLDER="/personal/aelshafee_horus_edu_eg/Documents/AIE_Docs"
export SUPABASE_DB_URL="postgresql+psycopg://postgres.vkcedjubluzooadtvtci:NxdjC2p.Z%40qR%2B76@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require"
python3 -m flask run --port=5003 &
cd ..

echo "All systems started! Gateway is running on http://127.0.0.1:5000"
echo "Press Ctrl+C to stop all."
wait
