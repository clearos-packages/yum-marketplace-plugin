Name: yum-marketplace-plugin
Version: 2.1
Release: 6%{?dist}
Summary: Yum plugin to access ClearCenter Marketplace
Group: System Environment/Base
License: GPLv3
URL: http://www.clearfoundation.com
Source: %{name}-%{version}.tar.gz
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
%config(replace) %{_sysconfdir}/yum/pluginconf.d/clearcenter-marketplace.conf
/usr/lib/yum-plugins/clearcenter-marketplace.*

%changelog
* Fri Sep 11 2015 ClearCenter <developer@clearcenter.com> - 2.1-1
- 0004972: Remove hard coded API version and add software_id

* Wed Sep 2 2015 ClearCenter <developer@clearcenter.com> - 2.1-2
- Update how pkgapi is being called

* Tue Sep 1 2015 ClearCenter <developer@clearcenter.com> - 2.1-1
- Switch to API 1.2
- Refactor header parsing
- Include dependant packages in list of available packages

* Wed Aug 26 2015 ClearCenter <developer@clearcenter.com> - 2.0-5
- Don't include headers in private repos
- Global headers override repo headers
- Add url to list if it includes $basearch
- Ensure repo directories get created in cache directory
- Clean up repositories when done

* Wed Aug 26 2015 ClearCenter <developer@clearcenter.com> - 2.0-4
- Don't require system to be registered

* Thu Jul 30 2015 ClearCenter <developer@clearcenter.com> - 2.0-3
- Add ability to auth single repos

* Wed Jul 29 2015 ClearCenter <developer@clearcenter.com> - 2.0-2
- Exclude packages we don't have permission to install
- Allow setting gpgkey

* Wed Jul 29 2015 ClearCenter <developer@clearcenter.com> - 2.0-1
- Prep plugin for new 1.2 API
- Allow use of mirrorlist
- Allow repos to use yum variable expansion ($releasever, $basearch)
- Allow repos to be enabled/disabled via cmdline

* Wed Jan 28 2015 ClearCenter <developer@clearcenter.com> - 1.9-1
- Extract version for release file

* Tue Mar 11 2014 ClearCenter <developer@clearcenter.com> - 1.8-1
- Reverted to CORE plugin type, moved enablebeta flag to config.

* Wed Mar 05 2014 ClearCenter <developer@clearcenter.com> - 1.7-1
- Re-enabled private BETA repository support

* Wed Dec 18 2013 ClearCenter <developer@clearcenter.com> - 1.6-1
- Reverted private BETA repository support

* Tue Oct 29 2013 ClearCenter <developer@clearcenter.com> - 1.5-1
- Added private BETA repository support

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
