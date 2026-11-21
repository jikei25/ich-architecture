FROM python:3.12-slim
RUN pip install --no-cache-dir pydicom==3.0.1 pynetdicom==3.0.4 numpy==2.3.4 nibabel==5.3.2
COPY load_nifti.py mock_ai.py /usr/local/bin/
ENTRYPOINT ["python", "/usr/local/bin/load_nifti.py"]
