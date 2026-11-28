FROM python:3.12-slim

# CPU-only torch keeps the staging image small; a GPU server uses the CUDA wheel instead.
# monailabel is installed without its optional heavy dependencies (SAM2, MLflow, OpenSlide).
RUN pip install --no-cache-dir torch==2.15.0 torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir --no-deps monailabel==0.8.8 \
 && pip install --no-cache-dir "monai[nibabel,ignite,itk,skimage,psutil,tqdm,tensorboard]==1.6.2" \
      fastapi uvicorn starlette pydantic pydantic-settings python-dotenv python-multipart httpx \
      schedule dicomweb-client timeloop expiringdict expiring_dict cachetools watchdog \
      pydicom highdicom==0.29.0 pynetdicom pynrrd SimpleITK requests requests-toolbelt pyyaml \
      filelock passlib pyjwt bcrypt einops scipy shapely google-auth girder-client

# /studies stays empty: the inference server receives each volume in the request and keeps nothing.
RUN mkdir /studies
COPY app /app
WORKDIR /app
ENTRYPOINT ["monailabel", "start_server", "--app", "/app"]
