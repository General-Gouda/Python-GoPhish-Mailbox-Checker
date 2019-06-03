<#
.SYNOPSIS
    New Azure Application Automation Script
.DESCRIPTION
    This script will create a new Azure AD Application, set Mail.ReadWrite
    API permissions, create a new client secret, create the Service Principal,
    grant Admin consent to the application and return the useful information
    (such as the secret) in the console window.
.NOTES
    Created by Matt Marchese

    To extract a list of App Roles connect to AzureAD and run this:
    Get-AzureADServicePrincipal -SearchString 'Microsoft Graph' | select -ExpandProperty AppRoles | select Value, Id

    To extract a list of Oauth2 Permission scopes run this:
    Get-AzureADServicePrincipal -SearchString 'Microsoft Graph' | select -ExpandProperty Oauth2Permissions | select Value, Id

    Version: 2019.03.26
#>

[CmdletBinding()]
param
(
    [Parameter(Mandatory=$true)]
    [string]$ApplicationName,

    [Parameter(Mandatory=$true)]
    [AllowNull()]
    [AllowEmptyCollection()]
    [string[]]$APIAppRoles,

    [Parameter(Mandatory=$true)]
    [AllowNull()]
    [AllowEmptyCollection()]
    [string[]]$APIOauth2Permissions
)

if (!(Get-Module -ListAvailable AzureAD))
{
    Install-Module AzureAD -Scope CurrentUser -Force
}

if (!(Get-Module -ListAvailable AzureRM))
{
    Install-Module AzureRM -Scope CurrentUser -Force
}

Import-Module AzureAD, AzureRm

"Authenticating to AzureAD module.`nAuthentication pop up window may appear behind IDE!"
Connect-AzureAD

$usefulInformation = [PSCustomObject]@{
    TenantId = (Get-AzureADTenantDetail).ObjectId
    ClientId = ""
    ClientSecret = ""
}

"Creating new application in Azure AD"
$newAppParams = @{
    DisplayName = $ApplicationName
    IdentifierUris = "https://localhost/$([Guid]::NewGuid().toString())"
    Homepage = "https://localhost/$([Guid]::NewGuid().toString())"
}

if (Get-AzureADApplication -SearchString $newAppParams.DisplayName)
{
    "An application with that name already exists. Retrieving info from existing app."
    $newAzureApp = Get-AzureADApplication -SearchString $newAppParams.DisplayName
}
else
{
    $newAzureApp = New-AzureADApplication @newAppParams -ErrorAction Stop
}

$usefulInformation.ClientId = $newAzureApp.AppId

"Gathering existing Microsoft Graph Service Principal Information."
$microsoftGraphServicePrincipal = Get-AzureADServicePrincipal -SearchString 'Microsoft Graph'

$resourceAccessList = @()

if ($APIAppRoles)
{
    "Looking up App Role IDs that match specified App Roles."

    $allApiRolePermissions = Get-AzureADServicePrincipal -All $true |
        Select-Object -ExpandProperty AppRoles |
            Select-Object -Unique

    foreach ($APIAppRole in $APIAppRoles)
    {
        $apiRolePermissionsInfo = $allApiRolePermissions | Where-Object {$_.value -match $APIAppRole}

        if (!$apiRolePermissionsInfo)
        {
            $apiRoleId = Read-Host "Please input GUID for '$APIAppRole' API role permissions in your tenant."
        }
        else
        {
            $apiRoleId = $apiRolePermissionsInfo.Id
        }

        $resourceAccess = New-Object Microsoft.Open.AzureAD.Model.ResourceAccess
        $resourceAccess.Id = $apiRoleId
        $resourceAccess.Type = "Role"

        $resourceAccessList += $resourceAccess
    }
}

if ($APIOauth2Permissions)
{
    "Looking up Oauth2 Permission IDs that match specified Oauth2 Permissions."

    $allApiOauth2PermissionInfo = Get-AzureADServicePrincipal -All $true |
        Select-Object -ExpandProperty AppRoles |
            Select-Object -Unique

    foreach ($APIOauth2Permission in $APIOauth2Permissions)
    {
        $apiOauth2PermissionInfo = $allApiOauth2PermissionInfo | Where-Object {$_.value -match $APIOauth2Permission}

        if (!$apiOauth2PermissionInfo)
        {
            $apiOauth2Id = Read-Host "Please input GUID for '$APIOauth2Permission' API Oauth2 Permissions in your tenant."
        }
        else
        {
            $apiOauth2Id = $apiOauth2PermissionInfo.Id
        }

        $resourceAccess = New-Object Microsoft.Open.AzureAD.Model.ResourceAccess
        $resourceAccess.Id = $apiOauth2Id
        $resourceAccess.Type = "Scope"

        $resourceAccessList += $resourceAccess
    }
}

$AzureMgmtAccess = New-Object -TypeName "Microsoft.Open.AzureAD.Model.RequiredResourceAccess"
$AzureMgmtAccess.ResourceAccess = $resourceAccess
$AzureMgmtAccess.ResourceAppId = $microsoftGraphServicePrincipal.AppId

"Applying resource access object to newly created application."
Set-AzureADApplication -ObjectId $newAzureApp.ObjectId -RequiredResourceAccess @($AzureMgmtAccess)

"Creating new secret key for application access"
$appKeySecret = New-AzureADApplicationPasswordCredential -ObjectId $newAzureApp.ObjectId -CustomKeyIdentifier "App_Password"

$usefulInformation.ClientSecret = $appKeySecret.Value

"Creating new service principal for application"
$servicePrincipalInfo = New-AzureADServicePrincipal -AppId $newAzureApp.AppId -Tags @("WindowsAzureActiveDirectoryIntegratedApp")

"Granting Admin Consent to new Azure AD application"
"Authenticating to AzureRM module.`nAuthentication pop up window may appear behind IDE!"
$res = Login-AzureRmAccount

$context = Get-AzureRmContext
$tenantId = $context.Tenant.Id
$refreshToken = @($context.TokenCache.ReadItems() | Where-Object {$_.tenantId -eq $tenantId -and $_.ExpiresOn -gt (Get-Date)})[0].RefreshToken
$body = "grant_type=refresh_token&refresh_token=$($refreshToken)&resource=74658136-14ec-4630-ad9b-26e160ff0fc6"
$apiToken = Invoke-RestMethod "https://login.windows.net/$tenantId/oauth2/token" -Method POST -Body $body -ContentType 'application/x-www-form-urlencoded'

$header = @{
    'Authorization' = 'Bearer ' + $apiToken.access_token
    'X-Requested-With'= 'XMLHttpRequest'
    'x-ms-client-request-id'= [guid]::NewGuid()
    'x-ms-correlation-id' = [guid]::NewGuid()
}

$url = "https://main.iam.ad.ext.azure.com/api/RegisteredApplications/$($newAzureApp.AppId)/Consent?onBehalfOfAll=true"

$response = Invoke-WebRequest -Uri $url -Headers $header -Method POST -ErrorAction Stop

"Response code: $($response.StatusCode)"

"`n**SENSITIVE INFORMATION!!**`nCopy this somewhere secure!!:"
$usefulInformation |
    Get-Member -MemberType Noteproperty |
        Select-Object -ExpandProperty Name |
            ForEach-Object {
                $propName = $_
                "  - $propName : $($usefulInformation.$propname)"
            }
"`n"
