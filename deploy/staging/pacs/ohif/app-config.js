/** OHIF viewer reading the lab archive (AE DCM4CHEE) over DICOMweb, through the same-origin proxy. */
const archive = `${window.location.origin}/dcm4chee-arc/aets/DCM4CHEE`;

window.config = {
  routerBasename: null,
  extensions: [],
  modes: [],
  showStudyList: true,
  maxNumberOfWebWorkers: 3,
  showLoadingIndicator: true,
  strictZSpacingForVolumeViewport: true,
  defaultDataSourceName: 'dcm4chee',
  dataSources: [
    {
      namespace: '@ohif/extension-default.dataSourcesModule.dicomweb',
      sourceName: 'dcm4chee',
      configuration: {
        friendlyName: 'dcm4chee lab archive',
        name: 'dcm4chee',
        qidoRoot: `${archive}/rs`,
        wadoRoot: `${archive}/rs`,
        wadoUriRoot: `${archive}/wado`,
        qidoSupportsIncludeField: true,
        supportsReject: true,
        imageRendering: 'wadors',
        thumbnailRendering: 'wadors',
        enableStudyLazyLoad: true,
        supportsFuzzyMatching: true,
        supportsWildcard: true,
        omitQuotationForMultipartRequest: true,
        bulkDataURI: { enabled: true },
      },
    },
  ],
};
