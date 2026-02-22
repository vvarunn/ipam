import pandas as pd
import ipaddress

# Read the CSV
df = pd.read_csv('test_vlans.csv')

# Function to fix CIDR (convert host address to network address)
def fix_cidr(cidr_str):
    try:
        cidr_str = str(cidr_str).strip().replace('\t', '').replace('\n', '')
        if not cidr_str or cidr_str == 'nan':
            return None
        # Use strict=False to convert host address to network address
        net = ipaddress.ip_network(cidr_str, strict=False)
        return str(net)
    except:
        return None

# Fix CIDR column
df['cidr'] = df['cidr'].apply(fix_cidr)

# Clean gateway column
df['gateway'] = df['gateway'].apply(lambda x: str(x).strip().replace('\t', '').replace('\n', '') if pd.notna(x) and str(x) != 'nan' else '')

# Remove rows with missing data
df = df.dropna(subset=['vlan_id', 'cidr'])

# Save cleaned file
df.to_csv('test_vlans_fixed.csv', index=False)
print(f'Fixed {len(df)} rows')
