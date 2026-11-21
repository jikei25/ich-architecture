FROM orthancteam/orthanc:26.9.1
# highdicom requires pyjpegls, which has no wheel for the image's Python 3.14; uncompressed SEG does not use it.
RUN pip3 install --no-cache-dir --break-system-packages \
      numpy==2.3.4 nibabel==5.3.2 pydicom==3.0.1 pillow==13.0.0 typing-extensions==4.16.0 packaging==26.0 \
 && pip3 install --no-cache-dir --break-system-packages --no-deps highdicom==0.29.0
COPY plugin/ai_bridge.py plugin/nifti_bridge.py /plugin/
