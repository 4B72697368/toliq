// Get your spreadsheet ID from the URL:
// Add this at the top of the file
const SPREADSHEET_ID = '1ga74Ug3PxZw9DSPAhwg07d_GYR2RXkTSyFMYeNhc-uU';
// GET endpoint for retrieving sheet data
function doGet(e) {
  Logger.log('GET Request received:', e);
  
  const action = e.parameter.action || 'listSheets';
  const sheetName = e.parameter.sheetName;
  
  switch (action) {
    case 'listSheets':
      return handleListSheets();
    case 'readSheet':
      return handleReadSheet(sheetName);
    default:
      return jsonResponse({ error: 'Unknown action' });
  }
}

// POST endpoint for sheet operations
function doPost(e) {
  Logger.log('Received POST request:', e.postData?.contents);
  
  try {
    const payload = JSON.parse(e.postData.contents);
    const action = payload.action;
    const data = payload.data;
    
    switch (action) {
      case 'writeCells':
        return handleWriteCells(data);
      default:
        return jsonResponse({ error: 'Unknown action' });
    }
  } catch (error) {
    return jsonResponse({ error: 'Invalid request: ' + error.message });
  }
}

// Response helper
function jsonResponse(data) {
  return ContentService.createTextOutput(JSON.stringify(data, null, 2))
    .setMimeType(ContentService.MimeType.JSON);
}

// Get A1 notation for a cell
function getA1Notation(row, col) {
  let a1 = '';
  while (col > 0) {
    let modulo = (col - 1) % 26;
    a1 = String.fromCharCode(65 + modulo) + a1;
    col = Math.floor((col - modulo) / 26);
  }
  return a1 + row;
}

// Sheet operation handlers
function handleListSheets() {
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const sheets = ss.getSheets();
    
    const sheetInfo = sheets.map(sheet => ({
      name: sheet.getName(),
      id: sheet.getSheetId(),
      numRows: sheet.getLastRow(),
      numCols: sheet.getLastColumn()
    }));
    
    return jsonResponse({
      success: true,
      sheets: sheetInfo
    });
  } catch (error) {
    return jsonResponse({ error: 'Failed to list sheets: ' + error.message });
  }
}

function handleReadSheet(sheetName) {
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const sheet = sheetName ? ss.getSheetByName(sheetName) : ss.getSheets()[0];
    
    if (!sheet) {
      return jsonResponse({ error: 'Sheet not found' });
    }
    
    const lastRow = sheet.getLastRow();
    const lastCol = sheet.getLastColumn();
    
    if (lastRow === 0 || lastCol === 0) {
      return jsonResponse({
        success: true,
        sheetName: sheet.getName(),
        data: {}
      });
    }
    
    const range = sheet.getRange(1, 1, lastRow, lastCol);
    const values = range.getValues();
    const formulas = range.getFormulas();
    
    // Create a clean dictionary format
    const cellData = {};
    for (let row = 0; row < values.length; row++) {
      for (let col = 0; col < values[row].length; col++) {
        const a1Notation = getA1Notation(row + 1, col + 1);
        const hasFormula = formulas[row][col] !== '';
        cellData[a1Notation] = {
          value: values[row][col],
          ...(hasFormula && { formula: formulas[row][col] })
        };
      }
    }
    
    return jsonResponse({
      success: true,
      sheetName: sheet.getName(),
      data: cellData
    });
  } catch (error) {
    return jsonResponse({ error: 'Failed to read sheet: ' + error.message });
  }
}

function handleWriteCells(data) {
  if (!data.cells || typeof data.cells !== 'object') {
    return jsonResponse({ error: 'Cells object is required' });
  }
  
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const sheet = data.sheetName ? ss.getSheetByName(data.sheetName) : ss.getSheets()[0];
    
    if (!sheet) {
      return jsonResponse({ error: 'Sheet not found' });
    }
    
    // Process each cell update
    const updates = [];
    for (const [a1Notation, cellData] of Object.entries(data.cells)) {
      const range = sheet.getRange(a1Notation);
      if (cellData.formula) {
        range.setFormula(cellData.formula);
      } else {
        range.setValue(cellData.value);
      }
      updates.push(a1Notation);
    }
    
    return jsonResponse({
      success: true,
      updatedCells: updates
    });
  } catch (error) {
    return jsonResponse({ error: 'Failed to write cells: ' + error.message });
  }
}

// Simple test function
function testSheetOperations() {
  Logger.log('Starting sheet operations test...');
  
  // Test 1: List all sheets
  Logger.log('\nTest 1: List sheets');
  const listTest = doGet({
    parameter: {
      action: 'listSheets'
    }
  });
  Logger.log('List sheets response: ' + listTest.getContent());
  
  // Test 2: Read sheet content
  Logger.log('\nTest 2: Read sheet');
  const readTest = doGet({
    parameter: {
      action: 'readSheet'
    }
  });
  Logger.log('Read sheet response: ' + readTest.getContent());
  
  // Test 3: Write to cells
  Logger.log('\nTest 3: Write cells');
  const writeTest = doPost({
    postData: {
      contents: JSON.stringify({
        action: 'writeCells',
        data: {
          cells: {
            'A1': { value: 'Test' },
            'B1': { formula: '=SUM(C1:D1)' },
            'C1': { value: 10 },
            'D1': { value: 20 }
          }
        }
      })
    }
  });
  Logger.log('Write cells response: ' + writeTest.getContent());
  
  return 'Tests completed';
}

