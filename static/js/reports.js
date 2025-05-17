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
    function fetchAndDisplayPingResults(serverId) {
        let apiUrl = '/api/results/';
        if (serverId) {
            apiUrl += `${serverId}/`;
        }
        apiUrl += 'ping';

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
            .then(data => {
                if (data.length === 0) {
                    pingResultsTableDiv.innerHTML = '<p>暂无 Ping 测试结果。</p>';
                    return;
                }

                // Build the Ping results table HTML
                // 构建 Ping 结果表格的 HTML
                let tableHtml = '<table class="table is-striped is-narrow is-fullwidth"><thead><tr>';
                tableHtml += '<th>时间</th>';
                tableHtml += '<th>发送</th>';
                tableHtml += '<th>接收</th>';
                tableHtml += '<th>丢包率</th>';
                tableHtml += '<th>最小 RTT</th>';
                tableHtml += '<th>平均 RTT</th>';
                tableHtml += '<th>最大 RTT</th>';
                tableHtml += '<th>原始结果</th>';
                tableHtml += '</tr></thead><tbody>';

                data.forEach(result => {
                    tableHtml += '<tr>';
                    tableHtml += `<td>${new Date(result.test_time).toLocaleString()}</td>`;
                    // 使用新的字段名称
                    // Use new field names
                    tableHtml += `<td>${result.packets_transmitted || 'N/A'}</td>`;
                    tableHtml += `<td>${result.packets_received || 'N/A'}</td>`;
                    // 格式化丢包率
                    // Format packet loss percentage
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

            })
            .catch(error => {
                console.error('Error fetching ping results:', error);
                pingResultsTableDiv.innerHTML = '<p class="has-text-danger">加载 Ping 结果时出错。</p>';
            });
    }

    // Function to fetch and display Traceroute results
    // 获取并显示 Traceroute 结果的函数
    function fetchAndDisplayTracerouteResults(serverId) {
        let apiUrl = '/api/results/';
        if (serverId) {
            apiUrl += `${serverId}/`;
        }
        apiUrl += 'traceroute';

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
            .then(data => {
                if (data.length === 0) {
                    tracerouteResultsTableDiv.innerHTML = '<p>暂无 Traceroute 测试结果。</p>';
                    return;
                }

                // Build the Traceroute results table HTML
                // 构建 Traceroute 结果表格的 HTML
                let tableHtml = '<table class="table is-striped is-narrow is-fullwidth"><thead><tr>';
                tableHtml += '<th>时间</th>';
                tableHtml += '<th>跳数</th>';
                tableHtml += '<th>主机/IP</th>';
                tableHtml += '<th>地理位置 (国家/城市)</th>';
                tableHtml += '<th>延迟</th>';
                tableHtml += '<th>详细输出</th>'; // Button column
                tableHtml += '</tr></thead><tbody>';

                data.forEach(result => {
                    // Each result might have multiple hops, use processed_hops directly
                    // 每个结果可能有多个跳，直接使用 processed_hops
                    if (result.processed_hops) { // 检查 processed_hops 是否存在
                         // Check if processed_hops exists
                         result.processed_hops.forEach(hop => {
                              hop.details.forEach(detail => {
                                   tableHtml += '<tr>';
                                   // Display time only for the first detail of the first hop of a result
                                   // 只在结果的第一个跳的第一个详情中显示时间
                                   // 注意：这里需要一个 helper function 来计算总行数
                                   // Note: a helper function is needed here to calculate the total number of rows
                                   const totalDetailsInResult = getDetailCountForProcessedResult(result); 
                                   if (hop.hop_number === result.processed_hops[0].hop_number && detail === hop.details[0]) {
                                        tableHtml += `<td rowspan="${totalDetailsInResult}">${new Date(result.test_time).toLocaleString()}</td>`;
                                   }
                                   tableHtml += `<td>${hop.hop_number}</td>`;
                                   tableHtml += `<td>${detail.host || 'N/A'}${detail.ip && detail.ip !== 'N/A' ? ` (${detail.ip})` : ''}</td>`;
                                   
                                   let locationText = 'N/A';
                                   // 优先使用 display_location (用于局域网 IP)，然后是 location 字段
                                   // Prefer display_location (for local IPs), then location field
                                   if (detail.display_location) {
                                        locationText = detail.display_location;
                                   } else if (detail.location) {
                                        locationText = detail.location.country || '';
                                        if (detail.location.city) {
                                             locationText += (locationText ? ', ' : '') + detail.location.city;
                                        }
                                   }
                                   tableHtml += `<td>${locationText}</td>`;
                                   tableHtml += `<td>${detail.rtt || 'N/A'}</td>`;

                                   // Add a button to view raw output only for the first detail of the first hop of a result
                                   // 只在结果的第一个跳的第一个详情中添加查看原始输出按钮
                                   if (hop.hop_number === result.processed_hops[0].hop_number && detail === hop.details[0]) {
                                        tableHtml += `<td rowspan="${totalDetailsInResult}"><button class="button is-small is-info view-raw-output" data-output="${encodeURIComponent(result.raw_output)}">查看详细</button></td>`;
                                   }
                                   tableHtml += '</tr>';
                              });
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

    // Add event listener to server select dropdown
    // 为服务器选择下拉列表添加事件监听器
    serverSelect.addEventListener('change', () => {
        const selectedServerId = serverSelect.value;
        // Determine the active tab and load data accordingly
        // 确定活动标签页并相应加载数据
        const activeTab = document.querySelector('.tabs li.is-active').dataset.tab;
        if (activeTab === 'ping') {
            fetchAndDisplayPingResults(selectedServerId);
        } else if (activeTab === 'traceroute') {
            fetchAndDisplayTracerouteResults(selectedServerId); // 调用 traceroute 函数
             // Call traceroute function
        }
    });

    // Initial data load when the page loads
    // 页面加载时初始化数据加载
    const initialSelectedServerId = serverSelect.value;
    const initialActiveTab = document.querySelector('.tabs li.is-active').dataset.tab;

    if (initialActiveTab === 'ping') {
        fetchAndDisplayPingResults(initialSelectedServerId);
    } else if (initialActiveTab === 'traceroute') {
        fetchAndDisplayTracerouteResults(initialSelectedServerId);
    }
}); 