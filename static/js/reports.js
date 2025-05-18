// JavaScript for tab functionality and data loading
// 标签页功能和数据加载的 JavaScript
document.addEventListener('DOMContentLoaded', function () {
    const tabs = document.querySelectorAll('.tabs li');
    const tabContentBoxes = document.querySelectorAll('.tab-content');
    const serverSelect = document.getElementById('server-select');
    const pingResultsTableDiv = document.getElementById('ping-results-table');
    const tracerouteResultsTableDiv = document.getElementById('traceroute-results-table'); // 获取 traceroute 结果 div 的引用
    const tracerouteDetailModal = document.getElementById('traceroute-detail-modal');
    const modalCloseButton = tracerouteDetailModal.querySelector('.delete');
    const closeModalButton = document.getElementById('close-modal');
    const tracerouteRawOutputPre = document.getElementById('traceroute-raw-output');

    // Function to open the modal
    // 打开模态框的函数
    function openModal(rawOutput) {
        tracerouteRawOutputPre.textContent = rawOutput; // 使用 textContent 安全地设置原始文本
        tracerouteDetailModal.classList.add('is-active');
    }

    // Function to close the modal
    // 关闭模态框的函数
    function closeModal() {
        tracerouteDetailModal.classList.remove('is-active');
        tracerouteRawOutputPre.textContent = ''; // 关闭时清空内容
    }

    // Add event listeners to modal close buttons
    // 为模态框关闭按钮添加事件监听器
    modalCloseButton.addEventListener('click', closeModal);
    closeModalButton.addEventListener('click', closeModal);
    // Close modal when clicking outside (on modal-background)
    // 点击外部 (模态框背景) 时关闭模态框
    tracerouteDetailModal.querySelector('.modal-background').addEventListener('click', closeModal);


    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(item => item.classList.remove('is-active'));
            tab.classList.add('is-active');

            const target = tab.dataset.tab;
            tabContentBoxes.forEach(box => {
                if (box.id === target + '-tab-content') {
                    box.classList.remove('is-hidden');
                } else {
                    box.classList.add('is-hidden');
                }
            });
             // When tab changes, load data for the current selected server and active tab
             // 标签页改变时，加载当前选定服务器和活动标签页的数据
            const selectedServerId = serverSelect.value;
            if (target === 'ping') {
                 fetchAndDisplayPingResults(selectedServerId);
            } else if (target === 'traceroute') {
                 fetchAndDisplayTracerouteResults(selectedServerId); // 调用 traceroute 函数
            }
        });
    });

    // Function to fetch and display Ping results
    // 获取并显示 Ping 结果的函数
    function fetchAndDisplayPingResults(serverId, page = 1, perPage = 10) {
        let apiUrl = '/api/results/';
        if (serverId) {
            apiUrl += `${serverId}/`;
        }
        apiUrl += `ping?page=${page}&per_page=${perPage}`;

        // Show loading message
        // 显示加载消息
        pingResultsTableDiv.innerHTML = '<p>加载 Ping 结果中...</p>';

        fetch(apiUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            // Expecting data to be an object with 'items' and pagination metadata
            // 期望 data 是一个包含 'items' 和分页元数据的对象
            .then(data => {
                // Check if there are items in the current page
                // 检查当前页是否有数据
                if (!data.items || data.items.length === 0) {
                    pingResultsTableDiv.innerHTML = '<p>暂无 Ping 测试结果。</p>';
                     // Still need to render pagination even if no items, to show total pages if any
                     // 即使没有数据，也需要渲染分页，以显示总页数（如果存在）
                    renderPaginationControls(data, 'ping', serverId); // Call pagination rendering function
                    return;
                }

                // Use data.items to build the Ping results table HTML
                // 使用 data.items 构建 Ping 结果表格的 HTML
                let tableHtml = '<table class="table is-striped is-narrow is-fullwidth"><thead><tr>';
                tableHtml += '<th>时间</th>';
                tableHtml += '<th>服务器主机名/IP</th>'; // Add Server Hostname column header
                tableHtml += '<th>服务器描述</th>'; // Add Server Description column header
                tableHtml += '<th>丢包率</th>';
                tableHtml += '<th>最小 RTT</th>';
                tableHtml += '<th>平均 RTT</th>';
                tableHtml += '<th>最大 RTT</th>';
                tableHtml += '<th>原始结果</th>';
                tableHtml += '</tr></thead><tbody>';

                data.items.forEach(result => {
                    tableHtml += '<tr>';
                    tableHtml += `<td>${new Date(result.test_time).toLocaleString()}</td>`;
                    tableHtml += `<td>${escapeHTML(result.server_hostname || 'N/A')}</td>`; // Display server hostname
                    tableHtml += `<td>${escapeHTML(result.server_description || 'N/A')}</td>`; // Display server description
                    // 使用新的字段名称
                    // Use new field names
                    tableHtml += `<td>${result.packet_loss_percent !== null ? result.packet_loss_percent.toFixed(1) + '%' : 'N/A'}</td>`;
                    // 格式化 RTT
                    // Format RTT
                    tableHtml += `<td>${result.min_rtt_ms !== null ? result.min_rtt_ms.toFixed(2) + ' ms' : 'N/A'}</td>`;
                    tableHtml += `<td>${result.avg_rtt_ms !== null ? result.avg_rtt_ms.toFixed(2) + ' ms' : 'N/A'}</td>`;
                    tableHtml += `<td>${result.max_rtt_ms !== null ? result.max_rtt_ms.toFixed(2) + ' ms' : 'N/A'}</td>`;
                    
                    // Ping 的查看详细按钮，使用 openModal 函数
                    // View raw output button for Ping, use openModal function
                    tableHtml += `<td><button class="button is-small is-info is-light view-raw-output" data-output="${encodeURIComponent(result.raw_output)}">查看详细</button></td>`; 
                    tableHtml += '</tr>';
                });

                tableHtml += '</tbody></table>';
                pingResultsTableDiv.innerHTML = tableHtml;
                
                // Add event listeners to view raw output buttons for Ping
                // 为 Ping 的查看原始输出按钮添加事件监听器
                pingResultsTableDiv.querySelectorAll('.view-raw-output').forEach(button => {
                    button.addEventListener('click', () => {
                         const rawOutput = decodeURIComponent(button.dataset.output);
                         openModal(rawOutput); // 调用 openModal 显示 Ping 的原始输出
                         // Call openModal to display raw output for Ping
                    });
                });

                // Render pagination controls after the table is built
                // 在表格构建后渲染分页控件
                renderPaginationControls(data, 'ping', serverId);

            })
            .catch(error => {
                console.error('Error fetching ping results:', error);
                pingResultsTableDiv.innerHTML = '<p class="has-text-danger">加载 Ping 结果时出错。</p>';
            });
    }

    // Function to fetch and display Traceroute results
    // 获取并显示 Traceroute 结果的函数
    function fetchAndDisplayTracerouteResults(serverId, page = 1, perPage = 10) {
        let apiUrl = '/api/results/';
        if (serverId) {
            apiUrl += `${serverId}/`;
        }
        apiUrl += `traceroute?page=${page}&per_page=${perPage}`;

        // Show loading message
        // 显示加载消息
        tracerouteResultsTableDiv.innerHTML = '<p>加载 Traceroute 结果中...</p>';

        fetch(apiUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
             // Expecting data to be an object with 'items' and pagination metadata
             // 期望 data 是一个包含 'items' 和分页元数据的对象
            .then(data => {
                // Check if there are items in the current page
                // 检查当前页是否有数据
                if (!data.items || data.items.length === 0) {
                    tracerouteResultsTableDiv.innerHTML = '<p>暂无 Traceroute 测试结果。</p>';
                     // Still need to render pagination even if no items
                     // 即使没有数据，也需要渲染分页
                     renderPaginationControls(data, 'traceroute', serverId); // Call pagination rendering function
                    return;
                }

                // Use data.items to build the Traceroute results table HTML
                // 使用 data.items 构建 Traceroute 结果表格的 HTML
                let tableHtml = '<table class="table is-striped is-narrow is-fullwidth"><thead><tr>';
                tableHtml += '<th>时间</th>';
                tableHtml += '<th>跳数</th>';
                tableHtml += '<th>主机/IP (详情)</th>'; // Modified header
                tableHtml += '<th>地理位置 (国家/城市) (详情)</th>'; // Modified header
                tableHtml += '<th>延迟 (详情)</th>'; // Modified header
                tableHtml += '<th>详细输出</th>'; // Button column
                tableHtml += '</tr></thead><tbody>';

                data.items.forEach(result => {
                    // Each result might have multiple hops, use processed_hops directly
                    // 每个结果可能有多个跳，直接使用 processed_hops
                    if (result.processed_hops) { // 检查 processed_hops 是否存在
                         // Check if processed_hops exists
                         
                         // Calculate the total number of hops for this result for rowspan
                         // 计算此结果的总跳点数以用于 rowspan
                         const totalHopsInResult = result.processed_hops.length;

                         result.processed_hops.forEach((hop, hopIndex) => {
                              // Check if all details for this hop are indicating no response (*)
                              // 检查此跳点的所有详细信息是否都表示没有响应 (*)
                              const isNoResponseHop = hop.details.length > 0 && hop.details.every(detail => 
                                   detail.host === '*' && detail.ip === 'N/A' && detail.rtt === 'N/A'
                              );

                              if (isNoResponseHop) {
                                   // If it's a no-response hop, skip rendering this row
                                   // 如果是没有响应的跳点，跳过渲染此行
                                   return; // equivalent to continue in forEach
                              }

                              tableHtml += '<tr>';
                                   
                              // Display time only for the first hop of a result
                              // 只在结果的第一个跳中显示时间
                              if (hopIndex === 0) {
                                   tableHtml += `<td rowspan="${totalHopsInResult}">${new Date(result.test_time).toLocaleString()}</td>`;
                              }

                              tableHtml += `<td>${hop.hop_number}</td>`;

                              // Combine details for Host/IP, Location, and RTT into single cells
                              // 将主机/IP、地理位置和延迟的详细信息组合到单个单元格中
                              let hostIpHtml = '';
                              let locationHtml = '';
                              let rttHtml = '';

                              hop.details.forEach((detail, detailIndex) => {
                                   if (detailIndex > 0) { // Add line break before adding subsequent details
                                        hostIpHtml += '<br>';
                                        locationHtml += '<br>';
                                        rttHtml += '<br>';
                                   }
                                   
                                   // Host/IP
                                   hostIpHtml += `${detail.host || 'N/A'}${detail.ip && detail.ip !== 'N/A' ? ` (${detail.ip})` : ''}`;

                                   // Location
                                   let locationText = 'N/A';
                                   if (detail.display_location) {
                                        locationText = detail.display_location;
                                   } else if (detail.location) {
                                        locationText = detail.location.country || '';
                                        if (detail.location.city) {
                                             locationText += (locationText ? ', ' : '') + detail.location.city;
                                        }
                                   }
                                   locationHtml += locationText;

                                   // RTT
                                   rttHtml += detail.rtt || 'N/A';
                              });

                              tableHtml += `<td>${hostIpHtml}</td>`;
                              tableHtml += `<td>${locationHtml}</td>`;
                              tableHtml += `<td>${rttHtml}</td>`;

                              // Add a button to view raw output only for the first hop of a result
                              // 只在结果的第一个跳中添加查看原始输出按钮
                              if (hopIndex === 0) {
                                   tableHtml += `<td rowspan="${totalHopsInResult}"><button class="button is-small is-info view-raw-output" data-output="${encodeURIComponent(result.raw_output)}">查看详细</button></td>`;
                              }

                              tableHtml += '</tr>';
                         });
                    } else {
                         // 处理 processed_hops 为空的情况，例如测试失败
                         // Handle case where processed_hops is empty, e.g., test failed
                         tableHtml += `<tr><td colspan="6">无法显示 Traceroute 详细结果。原始输出: ${escapeHTML(result.raw_output)}</td></tr>`;
                    }
                });

                tableHtml += '</tbody></table>';
                tracerouteResultsTableDiv.innerHTML = tableHtml;
                
                // Add event listeners to view raw output buttons for traceroute
                // 为 Traceroute 的查看原始输出按钮添加事件监听器
                tracerouteResultsTableDiv.querySelectorAll('.view-raw-output').forEach(button => {
                    button.addEventListener('click', () => {
                         const rawOutput = decodeURIComponent(button.dataset.output);
                         openModal(rawOutput);
                    });
                });

                // Render pagination controls after the table is built
                // 在表格构建后渲染分页控件
                renderPaginationControls(data, 'traceroute', serverId);

            })
            .catch(error => {
                console.error('Error fetching traceroute results:', error);
                tracerouteResultsTableDiv.innerHTML = '<p class="has-text-danger">加载 Traceroute 结果时出错。</p>';
            });
    }
    
    // Helper function to calculate total number of detail rows for a processed traceroute result
    // 计算处理后的 Traceroute 结果总详情行数的辅助函数
    function getDetailCountForProcessedResult(result) {
         let count = 0;
         if (result.processed_hops) {
              result.processed_hops.forEach(hop => {
                   count += hop.details.length;
              });
         }
         return count;
    }

    // Helper function to escape HTML entities (already added for ping)
    // 转义 HTML 实体的辅助函数 (已添加到 ping)
    function escapeHTML(str) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    // Function to render pagination controls
    // 渲染分页控件的函数
    // data: API 返回的分页对象
    // testType: 'ping' 或 'traceroute'
    // serverId: 当前选中的服务器 ID
    function renderPaginationControls(data, testType, serverId) {
        const paginationDivId = `${testType}-results-table`; // Get the ID of the results table div
        const resultsTableDiv = document.getElementById(paginationDivId);

        // Remove existing pagination controls if any
        // 移除已有的分页控件（如果存在）
        const existingPagination = resultsTableDiv.nextElementSibling; // Assuming pagination is right after the table div
        if (existingPagination && existingPagination.classList.contains('pagination-controls')) {
            existingPagination.remove();
        }

        if (data.pages <= 1) {
            // No need for pagination if there is only one page or less
            // 如果只有一页或更少，则不需要分页
            return;
        }

        let paginationHtml = '<nav class="pagination is-centered pagination-controls" role="navigation" aria-label="pagination"><ul class="pagination-list">';

        // Previous button
        // 上一页按钮
        paginationHtml += `<li><a class="pagination-previous ${!data.has_prev ? 'is-disabled' : ''}" data-page="${data.page - 1}" data-type="${testType}" data-server="${serverId}">上一页</a></li>`;

        // Page numbers
        // 页码
        // We will display a limited number of pages for simplicity
        // 为简化，我们只显示有限数量的页码
        const startPage = Math.max(1, data.page - 2);
        const endPage = Math.min(data.pages, data.page + 2);

        if (startPage > 1) {
            paginationHtml += `<li><a class="pagination-link" data-page="1" data-type="${testType}" data-server="${serverId}" aria-label="Goto page 1">1</a></li>`;
            if (startPage > 2) {
                paginationHtml += '<li><span class="pagination-ellipsis">&hellip;</span></li>';
            }
        }

        for (let i = startPage; i <= endPage; i++) {
            paginationHtml += `<li><a class="pagination-link ${i === data.page ? 'is-current' : ''}" data-page="${i}" data-type="${testType}" data-server="${serverId}" aria-label="Goto page ${i}" ${i === data.page ? 'aria-current="page"' : ''}>${i}</a></li>`;
        }

        if (endPage < data.pages) {
            if (endPage < data.pages - 1) {
                paginationHtml += '<li><span class="pagination-ellipsis">&hellip;</span></li>';
            }
            paginationHtml += `<li><a class="pagination-link" data-page="${data.pages}" data-type="${testType}" data-server="${serverId}" aria-label="Goto page ${data.pages}">${data.pages}</a></li>`;
        }

        // Next button
        // 下一页按钮
        paginationHtml += `<li><a class="pagination-next ${!data.has_next ? 'is-disabled' : ''}" data-page="${data.page + 1}" data-type="${testType}" data-server="${serverId}">下一页</a></li>`;

        paginationHtml += '</ul></nav>';

        // Insert pagination controls after the results table div
        // 在结果表格 div 之后插入分页控件
        resultsTableDiv.insertAdjacentHTML('afterend', paginationHtml);

        // Add event listeners to pagination links
        // 为分页链接添加事件监听器
        const paginationLinks = resultsTableDiv.nextElementSibling.querySelectorAll('.pagination-link, .pagination-previous, .pagination-next');
        paginationLinks.forEach(link => {
            if (!link.classList.contains('is-disabled')) {
                link.addEventListener('click', (event) => {
                    event.preventDefault();
                    const targetPage = parseInt(event.target.dataset.page);
                    const targetType = event.target.dataset.type;
                    const targetServer = event.target.dataset.server;
                    
                    // Fetch and display data for the target page
                    // 获取并显示目标页的数据
                    if (targetType === 'ping') {
                        fetchAndDisplayPingResults(targetServer, targetPage);
                    } else if (targetType === 'traceroute') {
                         fetchAndDisplayTracerouteResults(targetServer, targetPage);
                    }
                });
            }
        });
    }

    // Initial data load for the active tab and selected server
    // 活动标签页和选定服务器的初始数据加载
    // We need to get the initial active tab
    // 我们需要获取初始活动标签页
    const initialActiveTab = document.querySelector('.tabs li.is-active');
    const initialTarget = initialActiveTab ? initialActiveTab.dataset.tab : 'ping'; // Default to ping if no active tab
    const initialServerId = serverSelect.value;

    if (initialTarget === 'ping') {
        fetchAndDisplayPingResults(initialServerId);
    } else if (initialTarget === 'traceroute') {
        fetchAndDisplayTracerouteResults(initialServerId);
    }

    // Add event listener for server select change
    // 为服务器选择框添加事件监听器
    serverSelect.addEventListener('change', (event) => {
        const selectedServerId = event.target.value;
        // Determine the currently active tab
        // 确定当前活动标签页
        const activeTab = document.querySelector('.tabs li.is-active');
        const currentTestType = activeTab ? activeTab.dataset.tab : 'ping'; // Default to ping
        
        // Fetch and display data for the selected server and current active tab, starting from page 1
        // 获取并显示选定服务器和当前活动标签页的数据，从第一页开始
        if (currentTestType === 'ping') {
            fetchAndDisplayPingResults(selectedServerId, 1); // Start from page 1
        } else if (currentTestType === 'traceroute') {
             fetchAndDisplayTracerouteResults(selectedServerId, 1); // Start from page 1
        }
    });
}); 