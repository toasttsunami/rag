mkdir backend
mkdir backend/app
touch {backend/requirements.txt,backend/.env}
touch backend/app/{__init.py,main.py,models.py,services/__init.py}
mkdir backend/app/services
mkdir backend/app/user_management
touch backend/app/services/{__init.py,document_service.py,retrieval_service.py,rag_service.py}
touch backend/app/user_management/{__init.py,user_manager.py}