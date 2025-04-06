"use client"

import { useState } from "react"

type FunctionCallDisplayProps = {
  callResponses: string[]
}

export default function FunctionCallDisplay({
  callResponses,
}: FunctionCallDisplayProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)

  if (!callResponses || callResponses.length === 0) {
    return null
  }

  // Filter out io.continue and io.end function calls
  const filteredResponses = callResponses.filter(response => {
    // Check if this is an io.continue or io.end call
    if (response.includes('<function_call>') && 
        response.includes('<platform>io</platform>') && 
        (response.includes('<function>continue</function>') || 
         response.includes('<function>end</function>'))) {
      return false; // Filter out these control flow calls
    }
    return true; // Keep all other responses
  });

  // If there are no responses after filtering, don't render anything
  if (filteredResponses.length === 0) {
    return null;
  }

  const toggleExpand = (index: number) => {
    if (expandedIndex === index) {
      setExpandedIndex(null)
    } else {
      setExpandedIndex(index)
    }
  }

  return (
    <div className="w-full space-y-2 mt-2 text-sm">
      {filteredResponses.map((response, index) => {
        // Try to parse function calls from the response
        let functionCall = null
        let functionResult = null
        
        if (response.includes('<function_call>')) {
          try {
            // Extract platform
            const platformMatch = response.match(/<platform>([\s\S]*?)<\/platform>/)
            const platform = platformMatch ? platformMatch[1].trim() : null
            
            // Extract function name
            const functionMatch = response.match(/<function>([\s\S]*?)<\/function>/)
            const functionName = functionMatch ? functionMatch[1].trim() : null
            
            // Extract parameters
            const parameters: any[] = []
            const paramRegex = /<parameter\s+name="([^"]+)">([\s\S]*?)<\/parameter>/g
            let paramMatch
            
            while ((paramMatch = paramRegex.exec(response)) !== null) {
              const name = paramMatch[1]
              const valueStr = paramMatch[2]
              
              let value = valueStr
              // Try to parse JSON values
              try {
                if (valueStr.trim().startsWith('{') || valueStr.trim().startsWith('[')) {
                  // Log the problematic string for debugging
                  console.log("Attempting to parse JSON:", valueStr.substring(0, 200));
                  
                  // Try to clean the JSON string before parsing
                  let cleanedValue = valueStr;
                  
                  // Handle potential trailing commas which are a common JSON parse error
                  cleanedValue = cleanedValue.replace(/,\s*}/g, '}').replace(/,\s*\]/g, ']');
                  
                  try {
                    value = JSON.parse(cleanedValue);
                  } catch (innerError) {
                    console.error("Failed first parse attempt, trying with cleaned JSON:", innerError);
                    console.log("Cleaned value:", cleanedValue.substring(0, 200));
                    
                    // If that fails, keep the original string
                    value = valueStr;
                  }
                }
              } catch (e) {
                console.error("Failed to parse parameter value as JSON:", e);
                console.log("Problematic string:", valueStr.substring(0, 200));
                // Keep the original string value
                value = valueStr;
              }
              
              parameters.push({ name, value })
            }
            
            if (platform && functionName) {
              functionCall = {
                platform,
                function: functionName,
                parameters
              }
            }
          } catch (error) {
            console.error("Failed to parse XML function call:", error)
          }
        } else if (response.includes('<call:')) {
          try {
            // Handle legacy format for backwards compatibility
            const callMatch = response.match(/<call:(.*?)>/)
            if (callMatch && callMatch[1]) {
              functionCall = JSON.parse(callMatch[1])
            }
          } catch (error) {
            console.error("Failed to parse legacy function call:", error)
          }
        } else if (response.includes('<function_result>')) {
          try {
            // Extract platform
            const platformMatch = response.match(/<platform>([\s\S]*?)<\/platform>/)
            const platform = platformMatch ? platformMatch[1].trim() : null
            
            // Extract function name
            const functionMatch = response.match(/<function>([\s\S]*?)<\/function>/)
            const functionName = functionMatch ? functionMatch[1].trim() : null
            
            // Extract result - try both <result> and <r> tags
            let resultMatch = response.match(/<result>([\s\S]*?)<\/result>/)
            if (!resultMatch) {
              resultMatch = response.match(/<r>([\s\S]*?)<\/r>/)
            }
            
            const resultStr = resultMatch ? resultMatch[1] : ""
            
            if (platform && functionName) {
              let parsedResult = resultStr
              
              // Try to parse the result as JSON
              try {
                if (resultStr.trim().startsWith('{') || resultStr.trim().startsWith('[')) {
                  // Log the problematic string for debugging
                  console.log("Attempting to parse result JSON:", resultStr.substring(0, 200));
                  
                  // Try to clean the JSON string before parsing
                  let cleanedValue = resultStr;
                  
                  // Handle potential trailing commas which are a common JSON parse error
                  cleanedValue = cleanedValue.replace(/,\s*}/g, '}').replace(/,\s*\]/g, ']');
                  
                  try {
                    parsedResult = JSON.parse(cleanedValue);
                  } catch (innerError) {
                    console.error("Failed first result parse attempt, trying with cleaned JSON:", innerError);
                    console.log("Cleaned result value:", cleanedValue.substring(0, 200));
                    
                    // If that fails, keep the original string
                    parsedResult = resultStr;
                  }
                }
              } catch {
                // If it's not valid JSON, keep the string
                console.error("Failed to parse result as JSON");
                console.log("Problematic result string:", resultStr.substring(0, 200));
              }
              
              functionResult = {
                platform,
                function: functionName,
                result: parsedResult
              }
            }
          } catch (error) {
            console.error("Failed to parse XML function result:", error)
          }
        } else if (response.includes('Result of')) {
          try {
            // Extract platform, function name, and result
            const resultMatch = response.match(/Result of ([^:]+)\.([^:]+): (.*)/)
            if (resultMatch) {
              const [_, platform, func, resultStr] = resultMatch
              
              let parsedResult = resultStr
              try {
                // Try to parse the result as JSON
                parsedResult = JSON.parse(resultStr)
              } catch {
                // If it's not valid JSON, keep the string
              }
              
              functionResult = {
                platform,
                function: func,
                result: parsedResult
              }
            }
          } catch (error) {
            console.error("Failed to parse function result:", error)
          }
        } else if (response.includes('Function Call:')) {
          try {
            // Check if this is the new XML format
            if (response.includes('<function_call>')) {
              // Already handled by the first condition
              // This just prevents the old regex from running
            } else {
              // Handle the old format for backwards compatibility
              const callMatch = response.match(/Function Call: ([^\.]+)\.([^ ]+) with parameters: (.*)/)
              if (callMatch) {
                const [_, platform, func, paramsStr] = callMatch
                
                let params = []
                try {
                  // Try to parse the parameters as JSON
                  params = JSON.parse(paramsStr)
                } catch (e) {
                  console.error("Failed to parse parameters:", e)
                }
                
                functionCall = {
                  platform,
                  function: func,
                  parameters: params
                }
              }
            }
          } catch (error) {
            console.error("Failed to parse function call details:", error)
          }
        }

        const isExpanded = expandedIndex === index
        const shouldShowToggle = response.length > 150

        return (
          <div
            key={index}
            className="p-2 rounded bg-gray-700 border border-gray-600 overflow-hidden"
          >
            {functionCall ? (
              <div className="text-blue-300">
                <span className="font-bold">Function Call: </span>
                <span className="font-mono">
                  {functionCall.platform}.{functionCall.function}
                </span>
                {functionCall.parameters && functionCall.parameters.length > 0 && (
                  <div className="pl-4 mt-1">
                    <span className="text-gray-400">Parameters:</span>
                    <pre className="ml-2 text-xs overflow-x-auto">
                      {JSON.stringify(functionCall.parameters, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ) : functionResult ? (
              <div className="text-green-300">
                <span className="font-bold">Result: </span>
                <span className="font-mono">
                  {functionResult.platform}.{functionResult.function}
                </span>
                <pre className="mt-1 text-xs overflow-x-auto pl-4 text-gray-300">
                  {JSON.stringify(functionResult.result, null, 2)}
                </pre>
              </div>
            ) : (
              <div>
                <pre className={`whitespace-pre-wrap font-mono text-xs ${shouldShowToggle && !isExpanded ? "line-clamp-3" : ""}`}>
                  {response}
                </pre>
                {shouldShowToggle && (
                  <button
                    className="text-blue-400 hover:text-blue-300 text-xs mt-1"
                    onClick={() => toggleExpand(index)}
                  >
                    {isExpanded ? "Show less" : "Show more"}
                  </button>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
} 