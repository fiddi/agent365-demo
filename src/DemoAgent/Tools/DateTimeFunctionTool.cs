// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

using System.ComponentModel;

namespace DemoAgent.Tools
{
    public class DateTimeFunctionTool
    {
        [Description("Use this tool to get the current date and time")]
        public string GetCurrentDateTime()
        {
            return DateTimeOffset.Now.ToString("D", null);
        }
    }
}
