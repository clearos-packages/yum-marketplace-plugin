Name: yum-marketplace-plugin
Version: 1.4
Release: 1%{?dist}
Summary: Yum plugin to access ClearCenter Marketplace
Group: System Environment/Base
License: GPLv3
URL: http://www.clearfoundation.com
Source0: %{name}-%{version}.tar.gz
BuildRoot:	%(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)
BuildArch: noarch
Requires: python
Requires: yum

%description
Yum plugin to access ClearCenter Marketplace

%prep
%setup -q

%install
rm -rf %{buildroot}

mkdir -p %{buildroot}/%{_sysconfdir}/yum/pluginconf.d/ %{buildroot}/usr/lib/yum-plugins/

install -m 644 *.conf %{buildroot}/%{_sysconfdir}/yum/pluginconf.d/
install -m 644 *.py %{buildroot}/usr/lib/yum-plugins/

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%config(noreplace) %{_sysconfdir}/yum/pluginconf.d/clearcenter-marketplace.conf
/usr/lib/yum-plugins/clearcenter-marketplace.*

%changelog
* Thu Dec 06 2012 ClearCenter <developer@clearcenter.com> - 1.3-3
- Bumped web service version to 1.1

* Wed Aug 01 2012 ClearFoundation <developer@clearfoundation.com> - 1.3-2
- Added 'arch' parameter to request URI

* Tue May 08 2012 ClearFoundation <developer@clearfoundation.com> - 1.3-1
- Fixed build environment issue with mock

* Tue May 08 2012 ClearFoundation <developer@clearfoundation.com> - 1.2-1
- Fixed yum close hook part deux

* Mon May 07 2012 ClearFoundation <developer@clearfoundation.com> - 1.1-1
- Fixed yum close hook

* Wed May 02 2012 ClearFoundation <developer@clearfoundation.com> - 1.0-1
- Initial build
