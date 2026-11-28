"""MONAI Label app for intracranial hemorrhage.

One app, two models; `--conf models` picks which ones a server runs:
- hemorrhage_approved: the approved registry version, called by the gateway for every study; never trained here.
- hemorrhage_dev: drafts on demand for annotators, active learning and training on the reviewed labels.
"""
import os

import requests
from dicomweb_client import DICOMwebClient
from monailabel.config import settings
from monailabel.interfaces.app import MONAILabelApp
from monailabel.tasks.activelearning.first import First
from monailabel.tasks.activelearning.random import Random

from lib.hemorrhage import LABELS, HemorrhageInfer, HemorrhageTrain
from lib.registry import Registry
from lib.research import Orthanc, ResearchDatastore

APPROVED, DEV = "hemorrhage_approved", "hemorrhage_dev"


class MyApp(MONAILabelApp):
    def __init__(self, app_dir, studies, conf):
        self.models = conf.get("models", f"{APPROVED},{DEV}").split(",")
        self.registry = Registry(conf.get("registry", "/registry"))
        self.model_dir = conf.get("model_dir", "/models")
        self.dev_model = os.path.join(self.model_dir, f"{DEV}.pt")
        super().__init__(app_dir=app_dir, studies=studies, conf=conf, name="ich",
                         description="Intracranial hemorrhage segmentation", version="0.1", labels=LABELS)

    def init_datastore(self):
        if not self.studies.startswith("http"):
            return super().init_datastore()
        session = requests.Session()
        session.auth = (settings.MONAI_LABEL_DATASTORE_USERNAME, settings.MONAI_LABEL_DATASTORE_PASSWORD)
        client = DICOMwebClient(url=self.studies, session=session)
        orthanc = Orthanc(self.studies.removesuffix("/dicom-web"), session)
        return ResearchDatastore(client, orthanc, cache_path=settings.MONAI_LABEL_DICOMWEB_CACHE_PATH or None)

    def init_infers(self):
        infers = {}
        if APPROVED in self.models:
            infers[APPROVED] = HemorrhageInfer(
                paths=lambda: [self.registry.approved_model()],
                version=lambda: self.registry.approved_version() or "none",
                description="Approved model from the registry")
        if DEV in self.models:
            infers[DEV] = HemorrhageInfer(
                paths=lambda: [self.registry.approved_model(), self.dev_model],
                version=lambda: "dev" if os.path.exists(self.dev_model) else self.registry.approved_version(),
                description="Latest trained model, for drafts on demand")
        return infers

    def init_trainers(self):
        if DEV not in self.models:
            return {}
        return {DEV: HemorrhageTrain(
            model_dir=os.path.join(self.model_dir, "train"), publish_path=self.dev_model, registry=self.registry,
            datasets_root=self.conf.get("datasets", "/datasets"), description="Train on the reviewed labels")}

    def init_strategies(self):
        return {"first": First(), "random": Random()} if DEV in self.models else {}
