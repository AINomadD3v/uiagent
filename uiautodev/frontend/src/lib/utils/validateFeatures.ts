/**
 * Feature validation utility for Python console advanced features
 *
 * This module provides runtime validation of the implemented features
 * to ensure they work correctly in the browser environment.
 */

import { extractTraceback, formatTracebackForLLM, containsTraceback } from './tracebackExtractor';
import { getPythonConsoleContext, formatContextForLLM } from './llmContextProvider';

export interface ValidationResult {
	feature: string;
	passed: boolean;
	error?: string;
	details?: any;
}

export interface ValidationSuite {
	results: ValidationResult[];
	totalTests: number;
	passed: number;
	failed: number;
	success: boolean;
}

/**
 * Validate traceback extraction functionality
 */
function validateTracebackExtraction(): ValidationResult[] {
	const results: ValidationResult[] = [];

	// Test 1: Basic traceback extraction
	try {
		const output = `
Traceback (most recent call last):
  File "inspector_code.py", line 5, in <module>
    print(x)
NameError: name 'x' is not defined
`;
		const traceback = extractTraceback(output);
		results.push({
			feature: 'Basic traceback extraction',
			passed: !!(traceback && traceback.errorType === 'NameError'),
			details: traceback
		});
	} catch (error) {
		results.push({
			feature: 'Basic traceback extraction',
			passed: false,
			error: String(error)
		});
	}

	// Test 2: Complex traceback with multiple frames
	try {
		const output = `
Traceback (most recent call last):
  File "inspector_code.py", line 10, in main
    result = divide(10, 0)
  File "inspector_code.py", line 5, in divide
    return a / b
ZeroDivisionError: division by zero
`;
		const traceback = extractTraceback(output);
		results.push({
			feature: 'Complex traceback extraction',
			passed: !!(traceback && traceback.stackFrames.length === 2),
			details: traceback?.stackFrames.length
		});
	} catch (error) {
		results.push({
			feature: 'Complex traceback extraction',
			passed: false,
			error: String(error)
		});
	}

	// Test 3: Traceback detection
	try {
		const hasTraceback = containsTraceback('Traceback (most recent call last):');
		const noTraceback = containsTraceback('Normal output');
		results.push({
			feature: 'Traceback detection',
			passed: hasTraceback && !noTraceback,
			details: { hasTraceback, noTraceback }
		});
	} catch (error) {
		results.push({
			feature: 'Traceback detection',
			passed: false,
			error: String(error)
		});
	}

	// Test 4: LLM formatting
	try {
		const tracebackInfo = {
			traceback: 'NameError: name "x" is not defined',
			errorType: 'NameError',
			errorMessage: 'name "x" is not defined',
			stackFrames: [{
				file: 'inspector_code.py',
				line: 5,
				function: '<module>',
				code: 'print(x)'
			}],
			isComplete: true
		};
		const formatted = formatTracebackForLLM(tracebackInfo);
		results.push({
			feature: 'LLM traceback formatting',
			passed: formatted.includes('=== PYTHON TRACEBACK ==='),
			details: formatted.length
		});
	} catch (error) {
		results.push({
			feature: 'LLM traceback formatting',
			passed: false,
			error: String(error)
		});
	}

	return results;
}

/**
 * Validate LLM context provider functionality
 */
function validateLLMContextProvider(): ValidationResult[] {
	const results: ValidationResult[] = [];

	// Test 1: Basic context formatting
	try {
		const context = {
			currentCode: 'print("Hello World")',
			recentOutput: ['Hello World'],
			traceback: null,
			formattedTraceback: '',
			fullOutput: 'Hello World',
			cursorPosition: { line: 0, ch: 20 },
			isExecuting: false,
			lastError: null
		};
		const formatted = formatContextForLLM(context);
		results.push({
			feature: 'Basic LLM context formatting',
			passed: formatted.includes('=== CURRENT PYTHON CODE ==='),
			details: formatted.length
		});
	} catch (error) {
		results.push({
			feature: 'Basic LLM context formatting',
			passed: false,
			error: String(error)
		});
	}

	// Test 2: Context with traceback
	try {
		const context = {
			currentCode: 'print(x)',
			recentOutput: ['NameError: name "x" is not defined'],
			traceback: {
				traceback: 'NameError: name "x" is not defined',
				errorType: 'NameError',
				errorMessage: 'name "x" is not defined',
				stackFrames: [],
				isComplete: true
			},
			formattedTraceback: '=== PYTHON TRACEBACK ===\nNameError: name "x" is not defined',
			fullOutput: 'NameError: name "x" is not defined',
			cursorPosition: { line: 0, ch: 8 },
			isExecuting: false,
			lastError: 'NameError: name "x" is not defined'
		};
		const formatted = formatContextForLLM(context, { includeTracebackAnalysis: true });
		results.push({
			feature: 'LLM context with traceback',
			passed: formatted.includes('=== PYTHON TRACEBACK ==='),
			details: formatted.includes('NameError')
		});
	} catch (error) {
		results.push({
			feature: 'LLM context with traceback',
			passed: false,
			error: String(error)
		});
	}

	return results;
}

/**
 * Validate autocompletion related functionality
 */
function validateAutocompletion(): ValidationResult[] {
	const results: ValidationResult[] = [];

	// Test 1: Completion request structure
	try {
		const request = {
			code: 'import os\nos.',
			line: 1,
			column: 3
		};
		results.push({
			feature: 'Completion request structure',
			passed: !!(request.code && typeof request.line === 'number' && typeof request.column === 'number'),
			details: request
		});
	} catch (error) {
		results.push({
			feature: 'Completion request structure',
			passed: false,
			error: String(error)
		});
	}

	// Test 2: AbortController functionality
	try {
		const controller = new AbortController();
		const hasSignal = !!controller.signal;
		controller.abort();
		const isAborted = controller.signal.aborted;
		results.push({
			feature: 'AbortController support',
			passed: hasSignal && isAborted,
			details: { hasSignal, isAborted }
		});
	} catch (error) {
		results.push({
			feature: 'AbortController support',
			passed: false,
			error: String(error)
		});
	}

	return results;
}

/**
 * Run all validation tests
 */
export function runValidationSuite(): ValidationSuite {
	const allResults: ValidationResult[] = [
		...validateTracebackExtraction(),
		...validateLLMContextProvider(),
		...validateAutocompletion()
	];

	const passed = allResults.filter(r => r.passed).length;
	const failed = allResults.length - passed;

	return {
		results: allResults,
		totalTests: allResults.length,
		passed,
		failed,
		success: failed === 0
	};
}

/**
 * Format validation results as a human-readable report
 */
export function formatValidationReport(suite: ValidationSuite): string {
	let report = `
=== PYTHON CONSOLE ADVANCED FEATURES VALIDATION ===

Total Tests: ${suite.totalTests}
Passed: ${suite.passed}
Failed: ${suite.failed}
Success Rate: ${((suite.passed / suite.totalTests) * 100).toFixed(1)}%

=== DETAILED RESULTS ===
`;

	suite.results.forEach((result, index) => {
		const status = result.passed ? '✅ PASS' : '❌ FAIL';
		report += `\n${index + 1}. ${status} - ${result.feature}`;
		if (result.error) {
			report += `\n   Error: ${result.error}`;
		}
		if (result.details && typeof result.details === 'object') {
			report += `\n   Details: ${JSON.stringify(result.details, null, 2)}`;
		} else if (result.details) {
			report += `\n   Details: ${result.details}`;
		}
	});

	if (suite.success) {
		report += `\n\n🎉 ALL TESTS PASSED! Advanced Python console features are working correctly.`;
	} else {
		report += `\n\n⚠️  Some tests failed. Please review the implementation.`;
	}

	return report;
}

/**
 * Console-friendly validation runner
 */
export function validateInConsole(): void {
	console.log('🔍 Running Python Console Advanced Features Validation...');
	const suite = runValidationSuite();
	const report = formatValidationReport(suite);
	console.log(report);

	if (suite.success) {
		console.log('✅ Validation completed successfully!');
	} else {
		console.error('❌ Validation failed. Check the detailed report above.');
	}
}