const { Storage } = require('@google-cloud/storage');
const { Firestore } = require('@google-cloud/firestore');
const { parse } = require('junit2json');
const functions = require('@google-cloud/functions-framework');
const path = require('path');

const storage = new Storage();
const firestore = new Firestore({ projectId: 'moz-mobile-tools' });

functions.cloudEvent('ingestJUnitResults', async (cloudEvent) => {
  console.log(`Event ID: ${cloudEvent.id}`);
  console.log(`Event Type: ${cloudEvent.type}`);

  const file = cloudEvent.data;
  const bucketName = file.bucket;
  const filePath = file.name;

  // Check if the file is a FullJUnitReport.xml
  if (!filePath.endsWith('FullJUnitReport.xml')) {
    console.log(`Skipping non-JUnit report file: ${filePath}`);
    return;
  }

  const bucket = storage.bucket(bucketName);
  const blob = bucket.file(filePath);

  try {
    const [fileContents] = await blob.download();
    const xmlContent = fileContents.toString('utf-8');
    console.log('XML Content:', xmlContent); // Log the XML content to ensure it's being read correctly

    const jsonContent = await parse(xmlContent); // Ensure we're using `await` with `parse`
    console.log('Parsed JSON content:', JSON.stringify(jsonContent, null, 2)); // Log the parsed JSON content

    const testsuites = jsonContent.testsuite;

    // Save the testsuite document to Firestore
    // TODO: Define the Firestore document structure
    // for (const testsuite of testsuites) {
    //   const suiteName = testsuite.name;
    //   const testcases = testsuite.testcase;

    //   // Prepare an array to store the classnames for indexing
    //   const classnames = testcases.map(testcase => testcase.classname);

    //   // Save the testsuite document with indexed classnames
    //   await firestore.collection('aaron-test').add({
    //     suiteName,
    //     classnames, // Index classnames for querying
    //     testsuite
    //   });
    // }

    console.log(`JUnit report ingested successfully: ${filePath}`);
  } catch (err) {
    console.error(`Failed to ingest JUnit report: ${filePath}`, err);
  }
});
