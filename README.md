# Fixing terraform state issues with group memberships
> _This assumes you have `~/.oci/config` set up, valid tokens and keys._

* If someone has applied a terraform state change to a compartment, but do not have full access to the tenancy where the identity domain resides, thus messing up the state's perception of group memberships vs what is actually in OCI
* After the integration of IDCS into "OCI IAM with Application Domains" we've seen issues with terraform wanting to recreate user-group memberships

Typically, in both cases, we'll see:

```tf
# oci_identity_user_group_membership.api[0] will be created
+ resource "oci_identity_user_group_membership" "something" {
    + compartment_id = (known after apply)
    + group_id       = "ocid1.group.oc1..aaaaaa----REDACTED----4eeecf5bz3a"
    + id             = (known after apply)
    + inactive_state = (known after apply)
    + state          = (known after apply)
    + time_created   = (known after apply)
    + user_id        = "ocid1.user.oc1..aaaaaaa----REDACTED----mydvrvxehxq"
  }
 
# oci_identity_user_group_membership.lbadmin["something"] will be created
+ resource "oci_identity_user_group_membership" "lbadmin" {
    + compartment_id = (known after apply)
    + group_id       = "ocid1.group.oc1..aaaa----REDACTED----gm654glldjisq"
    + id             = (known after apply)
    + inactive_state = (known after apply)
    + state          = (known after apply)
    + time_created   = (known after apply)
    + user_id        = "ocid1.user.oc1..aaaa----REDACTED----gizadrz6d6fczq"
  }
  ```
When you run it you get a message that this already exists.

In our case the problem arises if you use terraform cloud as a state backend, but the one that applies a state change does not have sufficient privileges to apply state changes to the tenancy's root compartment. (where the DEFAULT (free) domain resides)
The state change is commited to terraform cloud, despite failing for OCI.

In our tf code we programmatically create the association of user/group.
The association object has its own OCID.
The OCID is on the form `ocid1.groupmembership.oc1..aaaaaaaa4efbam----REDACTED----jicjfh7uixca2wq5ma`

This OCID, however, is not visible in OCI's GUI, nor through the CLI. 

I registered an SR for this, and while waiting for Oracle to start working on it I started looking at OCI's Python SDK
The `list_user_group_memberships()` function in the identity_client returns the ID that we need.

## Scope
The changes in associations and tf's desire to recreate the associations basically affects all our tf workspaces.
If we perform a terraform apply on a workspace with the proposed changes above this terraform apply result in a conflict, (after four minutes and things timing out) where OCI says that you can't do this, the resource already exists.

## How to fix
When you encounter a terraform workspace that proposes the changes above, and (ready through the change-list,!) we need to generate state imports.

But,<br>
there are two ways, one can run terraform state import <resource> <ocid>  but this requires a terraform apply for each step, which is tedious and cumbersome.
We want to use [terraform import blocks](https://developer.hashicorp.com/terraform/language/import) to import multiple resources at once.

# How-to
In the terraform directory where the above changes are proposed
```bash
terraform plan -no-color > my_plan
cat my_plan | grep -E "membership.*will be created|user_id" | grep -Eo "oci\S*|module.*" |cut -d ' ' -f1 |sed 's/\"$//' > my_plan_ids
```
This will end up in a file with contents such as

```
oci_identity_user_group_membership.olam
ocid1.user.oc1..aaaaaaaaof3e5q----REDACTED----3tuhgkmtpx6nnoregsickciba
oci_identity_user_group_membership.restic["membership1"]
ocid1.user.oc1..aaaaaaaauhq2ixsb----REDACTED----k75ja7jxhqbuuo5zt7ut26a
oci_identity_user_group_membership.restic["membership2"]
ocid1.user.oc1..aaaaaaaaf2gwh3jx5h----REDACTED----nth3czoo5uwqckanpccbq
oci_identity_user_group_membership.restic["membership3"]
ocid1.user.oc1..aaaaaaaat2qcqznza----REDACTED----dgr6beaq2jynqwoye2ouba
oci_identity_user_group_membership.restic["membership4"]
ocid1.user.oc1..aaaaaaaaigme2et----REDACTED----kh225k7yafbp2u2ennohqdda
oci_identity_user_group_membership.restic["membership5"]
ocid1.user.oc1..aaaaaaaarqpo----REDACTED----jhtm7mgtpa7lqh6y72sc673ziia
oci_identity_user_group_membership.restic["membership6"]
ocid1.user.oc1..aaaaaaaa6peqqu----REDACTED----lepmtndjpokdhvq6fxk5xqoeq
```
The important thing is that there's a 1:1 relationship between `oci_identity_user_group_membership` resources and ocids which are user that we need to find the in-oci ocids for (the association ID)

(and because the next bit of code is written in my utter crap python it is a bit ticklish the file must start with a resource reference.

Clone https://github.com/trondstromme/oci_groupmembership

and run
```bash
$python filereader.py ~/path/to/your/terraform/my_plan_ids
```
This spits out the needed terraform import statements.
```tf
import{
    to = oci_identity_user_group_membership.----REDACTED----
    id = "ocid1.groupmembership.oc1..aaaaaaaa4kqr----REDACTED----r6ako4djdkyhd3a4yjxyepb7jmtoi5jbtqyf3q"
}
 
import{
    to = oci_identity_user_group_membership.----REDACTED----
    id = "ocid1.groupmembership.oc1..aaaaaaaa----REDACTED----k4253lobcsumzspntqh3selpcxdubyxfieuo5jgo6q"
}
 
import{
    to = oci_identity_user_group_membership.----REDACTED----["----REDACTED----"]
    id = "ocid1.groupmembership.oc1..aaaaaaaa6s6lkl----REDACTED----vx2p4mt66jtuep7wdhdxw6kkpo2cr66s27ma"
}
 
import{
    to = oci_identity_user_group_membership.----REDACTED----
    id = "ocid1.groupmembership.oc1..aaaaaaaau62mj----REDACTED----2u3w5zstr2gieas5bhtomdfkfyw6id26m2cea"
}
 
import{
    to = oci_identity_user_group_membership.----REDACTED----
    id = "ocid1.groupmembership.oc1..aaaaaaaaipxqaiu----REDACTED----kh5d5oxaash62pxawmpav2wlv6ufjestfeq"
}
```

(and please, no comments on the Python code, it may be python, but at the same time not python as someone who really knows python would write it, but....)

The generated statements above should be put in a file `imports.tf`  in your terraform project. This file is temporary in nature and should only be run once 
After having applied once you should _delete the file. 

## BIG GOTCHA!


if you do not see any import count when running terraform apply or terraform plan, this is a weird quirk.

You need to run terraform apply, once, without the imports.
It will spend four miinutes or, before it times out with a bunch of lengthy error messages saying the state is corrupt, the objects already exist in OCI.

This is OK, this is the failing state you want to start with, before fixing it.
Now the terraform.cloud state is appropriately aware that things are out of sync, and you can import the state.

## Recap
* generate a file with the plan
* run the grep regex/cut/sed to generate a new file with the resources and ocids to import
* check that it contains an even number of lines (see above)
* run terraform apply to fix the big red gotcha above
* run the filereader.py tool to generate import statements
* stick these in a file called imports.tf
* terraform apply (it should be quick, I promise!)
* delete imports.tf
* rinse and repeat for the next workspace
