/** @type {AppTypes.Config} */
// OHIF reads the PACS (dcm4chee) over DICOMweb through the same-origin proxy,
// so no CORS setup is needed: QIDO-RS for search, WADO-RS for metadata and
// pixels, STOW-RS for saving a corrected mask back.
const pacs = window.location.origin + '/dcm4chee-arc/aets/DCM4CHEE';

window.config = {
  name: 'ich-poc',
  routerBasename: null,
  extensions: [],
  modes: [],
  customizationService: {},
  showStudyList: true,
  maxNumberOfWebWorkers: 3,
  showWarningMessageForCrossOrigin: false,
  showCPUFallbackMessage: true,
  showLoadingIndicator: true,
  strictZSpacingForVolumeViewport: true,
  maxNumRequests: { interaction: 100, thumbnail: 5, prefetch: 25 },
  showErrorDetails: 'always',
  defaultDataSourceName: 'dcm4chee',
  dataSources: [
    {
      namespace: '@ohif/extension-default.dataSourcesModule.dicomweb',
      sourceName: 'dcm4chee',
      configuration: {
        friendlyName: 'dcm4chee PACS (PoC)',
        name: 'dcm4chee',
        qidoRoot: pacs + '/rs',
        wadoRoot: pacs + '/rs',
        wadoUriRoot: pacs + '/wado',
        qidoSupportsIncludeField: true,
        supportsReject: true,
        dicomUploadEnabled: true,
        imageRendering: 'wadors',
        thumbnailRendering: 'wadors',
        enableStudyLazyLoad: true,
        supportsFuzzyMatching: true,
        supportsWildcard: true,
        omitQuotationForMultipartRequest: true,
        bulkDataURI: { enabled: true, relativeResolution: 'studies' },
      },
    },
  ],
};
